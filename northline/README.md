# Northline

Offline prop desktop for an English-language series. One computer, shared windows and files. The signed-in user lives in `config/machine.json`.

## Open on another computer

Unzip `dist/Northline.zip` and double-click the program for that computer:

- Windows: `Northline.exe`
- Mac (Apple silicon): `Northline.app`
- Mac (Intel): `Northline-intel.app`
- Linux: `Northline`

The desktop opens in the browser. Close that window to quit. Flutter does not need to be installed. The first launch may ask you to allow the program.

Changing `config/machine.json` means building the zip again:

```bash
./pack.sh
```

## Develop

```bash
cd northline
flutter pub get
flutter run -d web-server --web-port 7357
```
