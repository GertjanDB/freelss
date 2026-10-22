package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestHandlerServesDesktopFiles(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "index.html"), []byte("<html><body>Hi</body></html>"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "app.wasm"), []byte("not really wasm"), 0o644); err != nil {
		t.Fatal(err)
	}

	rec := httptest.NewRecorder()
	handler(root, &pings{}).ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("index status %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), pingPath) {
		t.Fatalf("index missing ping: %s", rec.Body.String())
	}
	if got := rec.Header().Get("Content-Type"); got != "text/html; charset=utf-8" {
		t.Fatalf("index content type %q", got)
	}

	rec = httptest.NewRecorder()
	handler(root, &pings{}).ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/app.wasm", nil))
	if got := rec.Header().Get("Content-Type"); got != "application/wasm" {
		t.Fatalf("wasm content type %q", got)
	}

	rec = httptest.NewRecorder()
	handler(root, &pings{}).ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/../secret", nil))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("traversal status %d", rec.Code)
	}
}
