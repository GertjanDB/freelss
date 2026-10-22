# Northline

Offline prop desktop for an English-language series. One computer, shared windows and files. The signed-in user lives in `config/machine.json`.

```bash
cd northline
flutter pub get
flutter run -d web-server --web-port 7357
```

Open the localhost address Flutter prints. For a static build:

```bash
flutter build web
python3 -m http.server 7357 --directory build/web
```
