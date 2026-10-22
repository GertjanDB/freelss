#!/usr/bin/env bash
# Build a folder you can copy to another computer and open with a double-click.
set -euo pipefail
cd "$(dirname "$0")"

flutter build web --release --no-web-resources-cdn --pwa-strategy=none

stage="$(mktemp -d)"
cleanup() { rm -rf "$stage"; }
trap cleanup EXIT

dest="$stage/Northline"
mkdir -p "$dest/web"
cp -a build/web/. "$dest/web/"
find "$dest/web" -name '*.symbols' -delete

plist() {
  local app_dir="$1"
  mkdir -p "$app_dir/Contents/MacOS" "$app_dir/Contents/Resources"
  cat > "$app_dir/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Northline</string>
  <key>CFBundleDisplayName</key>
  <string>Northline</string>
  <key>CFBundleIdentifier</key>
  <string>ink.northline.desktop</string>
  <key>CFBundleVersion</key>
  <string>1.0.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  <key>CFBundleExecutable</key>
  <string>Northline</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
EOF
}

plist "$dest/Northline.app"
plist "$dest/Northline-intel.app"

(
  cd launcher
  CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -ldflags="-H windowsgui -s -w" -o "$dest/Northline.exe" .
  CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o "$dest/Northline" .
  CGO_ENABLED=0 GOOS=darwin GOARCH=arm64 go build -ldflags="-s -w" -o "$dest/Northline.app/Contents/MacOS/Northline" .
  CGO_ENABLED=0 GOOS=darwin GOARCH=amd64 go build -ldflags="-s -w" -o "$dest/Northline-intel.app/Contents/MacOS/Northline" .
)
chmod +x "$dest/Northline" "$dest/Northline.app/Contents/MacOS/Northline" "$dest/Northline-intel.app/Contents/MacOS/Northline"

mkdir -p dist
rm -f dist/Northline.zip
( cd "$stage" && zip -r -q "$OLDPWD/dist/Northline.zip" Northline )
echo "Wrote dist/Northline.zip"
