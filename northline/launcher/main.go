// Launcher for the Northline prop desktop.
// Double-click the program: it serves the built web app on this machine only
// and opens it in the browser. Closing the browser stops the program.
package main

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"
)

const pingPath = "/__northline/ping"

func main() {
	root, err := webRoot()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	if openIfAlreadyRunning() {
		return
	}

	listener, port, err := listen()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Northline could not start:", err)
		os.Exit(1)
	}

	state := &pings{}
	server := &http.Server{
		Handler: handler(root, state),
	}
	go func() {
		_ = server.Serve(listener)
	}()

	url := fmt.Sprintf("http://127.0.0.1:%d/", port)
	fmt.Println("Northline is open in your browser.")
	fmt.Println("Close the browser window to quit.")
	_ = openBrowser(url)

	deadline := time.Now().Add(45 * time.Second)
	for {
		time.Sleep(time.Second)
		seen, last := state.snapshot()
		if seen && time.Since(last) > 12*time.Second {
			_ = server.Close()
			return
		}
		if !seen && time.Now().After(deadline) {
			// The browser never connected. Keep serving until this window is closed.
			select {}
		}
	}
}

type pings struct {
	mu   sync.Mutex
	seen bool
	last time.Time
}

func (p *pings) mark() {
	p.mu.Lock()
	p.seen = true
	p.last = time.Now()
	p.mu.Unlock()
}

func (p *pings) snapshot() (bool, time.Time) {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.seen, p.last
}

func webRoot() (string, error) {
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	if resolved, err := filepath.EvalSymlinks(exe); err == nil {
		exe = resolved
	}
	dir := filepath.Dir(exe)
	candidates := []string{
		filepath.Join(dir, "web"),
		filepath.Join(dir, "..", "web"),
		filepath.Join(dir, "..", "Resources", "web"),
		filepath.Join(dir, "..", "..", "..", "web"),
	}
	for _, candidate := range candidates {
		info, err := os.Stat(filepath.Join(candidate, "index.html"))
		if err == nil && !info.IsDir() {
			return candidate, nil
		}
	}
	return "", fmt.Errorf("could not find the Northline web folder next to this program")
}

func listen() (net.Listener, int, error) {
	var last error
	for port := 7357; port < 7377; port++ {
		listener, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port))
		if err == nil {
			return listener, port, nil
		}
		last = err
	}
	return nil, 0, last
}

func openIfAlreadyRunning() bool {
	client := http.Client{Timeout: 400 * time.Millisecond}
	for port := 7357; port < 7377; port++ {
		url := fmt.Sprintf("http://127.0.0.1:%d%s", port, pingPath)
		response, err := client.Get(url)
		if err != nil {
			continue
		}
		response.Body.Close()
		if response.StatusCode == http.StatusNoContent {
			_ = openBrowser(fmt.Sprintf("http://127.0.0.1:%d/", port))
			return true
		}
	}
	return false
}

func handler(root string, state *pings) http.Handler {
	root = filepath.Clean(root)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == pingPath {
			state.mark()
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		rel := strings.TrimPrefix(r.URL.Path, "/")
		if rel == "" {
			rel = "index.html"
		}
		rel = filepath.Clean(rel)
		if rel == ".." || strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
			http.NotFound(w, r)
			return
		}
		full := filepath.Join(root, rel)
		if !strings.HasPrefix(filepath.Clean(full), root+string(os.PathSeparator)) && filepath.Clean(full) != root {
			http.NotFound(w, r)
			return
		}

		file, err := os.Open(full)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		defer file.Close()
		info, err := file.Stat()
		if err != nil || info.IsDir() {
			http.NotFound(w, r)
			return
		}

		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Content-Type", contentType(full))
		if filepath.Base(full) == "index.html" {
			body, err := io.ReadAll(file)
			if err != nil {
				http.Error(w, "could not read index", http.StatusInternalServerError)
				return
			}
			body = injectPing(body)
			http.ServeContent(w, r, info.Name(), info.ModTime(), strings.NewReader(string(body)))
			return
		}
		http.ServeContent(w, r, info.Name(), info.ModTime(), file)
	})
}

func injectPing(body []byte) []byte {
	const script = `<script>setInterval(function(){fetch("` + pingPath + `").catch(function(){})},3000)</script>`
	if strings.Contains(string(body), pingPath) {
		return body
	}
	updated := strings.Replace(string(body), "</body>", script+"</body>", 1)
	return []byte(updated)
}

func contentType(name string) string {
	switch strings.ToLower(filepath.Ext(name)) {
	case ".html":
		return "text/html; charset=utf-8"
	case ".js":
		return "text/javascript; charset=utf-8"
	case ".css":
		return "text/css; charset=utf-8"
	case ".json":
		return "application/json"
	case ".wasm":
		return "application/wasm"
	case ".svg":
		return "image/svg+xml"
	case ".png":
		return "image/png"
	case ".ico":
		return "image/x-icon"
	case ".txt":
		return "text/plain; charset=utf-8"
	default:
		return "application/octet-stream"
	}
}

func openBrowser(url string) error {
	var command *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		command = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		command = exec.Command("open", url)
	default:
		command = exec.Command("xdg-open", url)
	}
	return command.Start()
}
