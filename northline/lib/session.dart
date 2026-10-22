import 'dart:math' as math;

import 'package:flutter/widgets.dart';
import 'package:northline/machine.dart';
import 'package:northline/pnd_data.dart';
import 'package:northline/virtual_fs.dart';

enum AppKind { explorer, notepad, pnd }

enum WindowEdge { north, south, east, west, northEast, northWest, southEast, southWest }

class DeskWindow {
  DeskWindow({
    required this.id,
    required this.kind,
    required this.title,
    required this.left,
    required this.top,
    required this.width,
    required this.height,
  });

  final int id;
  final AppKind kind;
  String title;
  double left;
  double top;
  double width;
  double height;
  bool minimized = false;
  bool maximized = false;
  Rect? restore;

  String explorerPath = '';
  final List<String> history = [];
  String? selectedName;

  String? notepadPath;
  TextEditingController? text;
  TextEditingController? saveName;
  bool showSaveAs = false;
  String? status;

  TextEditingController? pndQuery;
  String? pndSelectedId;

  void dispose() {
    text?.dispose();
    saveName?.dispose();
    pndQuery?.dispose();
  }
}

/// One computer: windows, files, and the signed-in user.
class Session extends ChangeNotifier {
  Session(this.machine, this.fs);

  final MachineConfig machine;
  final VirtualFs fs;
  final List<DeskWindow> windows = [];
  bool startOpen = false;
  String? selectedIcon;
  int _nextId = 1;
  int _cascade = 0;

  bool isFocused(DeskWindow window) {
    return windows.isNotEmpty && identical(windows.last, window) && !window.minimized;
  }

  void toggleStart() {
    startOpen = !startOpen;
    notifyListeners();
  }

  void dismiss() {
    if (!startOpen && selectedIcon == null) return;
    startOpen = false;
    selectedIcon = null;
    notifyListeners();
  }

  void selectIcon(String id) {
    selectedIcon = id;
    startOpen = false;
    notifyListeners();
  }

  void openIcon(String id) {
    switch (id) {
      case 'explorer':
        openExplorer();
      case 'notepad':
        openNotepad();
      case 'pnd':
        openPnd();
    }
  }

  DeskWindow openExplorer() {
    final window = _spawn(AppKind.explorer, const Size(780, 500));
    _enterFolder(window, machine.documents, recordHistory: false);
    notifyListeners();
    return window;
  }

  DeskWindow openNotepad({String? path}) {
    if (path != null) {
      final existing = windows
          .where((window) => window.kind == AppKind.notepad && window.notepadPath == path)
          .firstOrNull;
      if (existing != null) {
        existing.text?.text = fs.read(path);
        existing.minimized = false;
        existing.title = _notepadTitle(path);
        existing.status = machine.displayPath(path);
        _bringToFront(existing);
        startOpen = false;
        notifyListeners();
        return existing;
      }
    }
    final window = _spawn(AppKind.notepad, const Size(640, 460));
    window.notepadPath = path;
    window.text = TextEditingController(text: path == null ? '' : fs.read(path));
    window.title = path == null ? 'Untitled - Notepad' : _notepadTitle(path);
    window.status = path == null ? 'Unsaved' : machine.displayPath(path);
    notifyListeners();
    return window;
  }

  DeskWindow openPnd() {
    final existing = windows.where((window) => window.kind == AppKind.pnd).firstOrNull;
    if (existing != null) {
      existing.minimized = false;
      _bringToFront(existing);
      startOpen = false;
      notifyListeners();
      return existing;
    }
    final window = _spawn(AppKind.pnd, const Size(960, 580));
    window.title = 'Police National Database - ${machine.shortName}';
    window.pndQuery = TextEditingController();
    notifyListeners();
    return window;
  }

  void focus(DeskWindow window) {
    final already = isFocused(window);
    if (!already) _bringToFront(window);
    if (startOpen || !already) {
      startOpen = false;
      notifyListeners();
    }
  }

  void close(DeskWindow window) {
    windows.remove(window);
    window.dispose();
    notifyListeners();
  }

  void minimize(DeskWindow window) {
    window.minimized = true;
    final other = windows.reversed.where((item) => !identical(item, window) && !item.minimized).firstOrNull;
    if (other != null) _bringToFront(other);
    notifyListeners();
  }

  void taskbarClick(DeskWindow window) {
    if (window.minimized || !isFocused(window)) {
      window.minimized = false;
      _bringToFront(window);
      startOpen = false;
      notifyListeners();
      return;
    }
    minimize(window);
  }

  void toggleMax(DeskWindow window) {
    if (window.maximized) {
      window.maximized = false;
      final previous = window.restore;
      if (previous != null) {
        window.left = previous.left;
        window.top = previous.top;
        window.width = previous.width;
        window.height = previous.height;
      }
    } else {
      window.restore = Rect.fromLTWH(window.left, window.top, window.width, window.height);
      window.maximized = true;
    }
    notifyListeners();
  }

  void moveBy(DeskWindow window, Offset delta, Size desktop) {
    if (window.maximized) return;
    window.left += delta.dx;
    window.top += delta.dy;
    window.top = window.top.clamp(0, math.max(0, desktop.height - 36));
    window.left = window.left.clamp(-window.width + 80, math.max(0, desktop.width - 48));
    notifyListeners();
  }

  void resize(DeskWindow window, WindowEdge edge, Offset delta, Size desktop) {
    if (window.maximized) return;
    var left = window.left;
    var top = window.top;
    var width = window.width;
    var height = window.height;
    const minWidth = 460.0;
    const minHeight = 300.0;

    if (edge == WindowEdge.east || edge == WindowEdge.northEast || edge == WindowEdge.southEast) {
      width += delta.dx;
    }
    if (edge == WindowEdge.south || edge == WindowEdge.southEast || edge == WindowEdge.southWest) {
      height += delta.dy;
    }
    if (edge == WindowEdge.west || edge == WindowEdge.northWest || edge == WindowEdge.southWest) {
      left += delta.dx;
      width -= delta.dx;
    }
    if (edge == WindowEdge.north || edge == WindowEdge.northEast || edge == WindowEdge.northWest) {
      top += delta.dy;
      height -= delta.dy;
    }
    if (width < minWidth) {
      if (edge == WindowEdge.west || edge == WindowEdge.northWest || edge == WindowEdge.southWest) {
        left -= minWidth - width;
      }
      width = minWidth;
    }
    if (height < minHeight) {
      if (edge == WindowEdge.north || edge == WindowEdge.northEast || edge == WindowEdge.northWest) {
        top -= minHeight - height;
      }
      height = minHeight;
    }
    top = top.clamp(0, math.max(0, desktop.height - 36));
    if (top + height > desktop.height) height = math.max(minHeight, desktop.height - top);

    window.left = left;
    window.top = top;
    window.width = width;
    window.height = height;
    notifyListeners();
  }

  void explorerBack(DeskWindow window) {
    if (window.history.isEmpty) return;
    window.explorerPath = window.history.removeLast();
    window.selectedName = null;
    window.title = _explorerTitle(window.explorerPath);
    notifyListeners();
  }

  void explorerUp(DeskWindow window) {
    final parent = fs.parentPath(window.explorerPath);
    if (parent == null) return;
    window.history.add(window.explorerPath);
    _enterFolder(window, parent, recordHistory: false);
    notifyListeners();
  }

  void explorerGo(DeskWindow window, String path) {
    window.history.add(window.explorerPath);
    _enterFolder(window, path, recordHistory: false);
    notifyListeners();
  }

  void selectExplorer(DeskWindow window, String name) {
    window.selectedName = name;
    notifyListeners();
  }

  void openExplorerNode(DeskWindow window, FsNode node) {
    if (node.isDirectory) {
      window.history.add(window.explorerPath);
      _enterFolder(window, node.path, recordHistory: false);
      notifyListeners();
      return;
    }
    openNotepad(path: node.path);
  }

  void openSelected(DeskWindow window) {
    final name = window.selectedName;
    if (name == null) return;
    final node = fs.list(window.explorerPath).where((item) => item.name == name).firstOrNull;
    if (node != null) openExplorerNode(window, node);
  }

  void saveNotepad(DeskWindow window) {
    final path = window.notepadPath;
    if (path == null) {
      beginSaveAs(window);
      return;
    }
    fs.writeFile(path, window.text?.text ?? '');
    window.status = 'Saved ${machine.displayPath(path)}';
    window.title = _notepadTitle(path);
    notifyListeners();
  }

  void beginSaveAs(DeskWindow window) {
    final suggested = window.notepadPath == null ? 'Notes.txt' : _base(window.notepadPath!);
    if (window.saveName == null) {
      window.saveName = TextEditingController(text: suggested);
    } else {
      window.saveName!.text = suggested;
    }
    window.showSaveAs = true;
    notifyListeners();
  }

  void commitSaveAs(DeskWindow window) {
    final raw = (window.saveName?.text ?? '').trim();
    if (raw.isEmpty) return;
    final safe = raw.replaceAll(RegExp(r'[\\/:*?"<>|]'), '').trim();
    if (safe.isEmpty) return;
    final fileName = safe.toLowerCase().endsWith('.txt') ? safe : '$safe.txt';
    final path = '${machine.documents}/$fileName';
    fs.writeFile(path, window.text?.text ?? '');
    window.notepadPath = path;
    window.title = _notepadTitle(path);
    window.status = 'Saved ${machine.displayPath(path)}';
    window.showSaveAs = false;
    notifyListeners();
  }

  void cancelSaveAs(DeskWindow window) {
    window.showSaveAs = false;
    notifyListeners();
  }

  void savePndRecord(DeskWindow window) {
    final id = window.pndSelectedId;
    if (id == null) return;
    final record = recordById(id);
    if (record == null) return;
    final path = '${machine.documents}/${recordFileName(record)}';
    fs.writeFile(path, recordFileText(record, machine));
    window.status = 'Saved ${machine.displayPath(path)}';
    notifyListeners();
  }

  void savePndSearch(DeskWindow window) {
    final query = window.pndQuery?.text ?? '';
    final results = filterRecords(query);
    final path = '${machine.documents}/${searchFileName(query)}';
    fs.writeFile(path, searchFileText(query, results, machine));
    window.status = 'Saved ${machine.displayPath(path)}';
    notifyListeners();
  }

  DeskWindow _spawn(AppKind kind, Size size) {
    final offset = (_cascade % 5) * 28.0;
    _cascade += 1;
    final window = DeskWindow(
      id: _nextId++,
      kind: kind,
      title: '',
      left: 56.0 + offset,
      top: 28.0 + offset,
      width: size.width,
      height: size.height,
    );
    windows.add(window);
    startOpen = false;
    selectedIcon = null;
    return window;
  }

  void _bringToFront(DeskWindow window) {
    windows.remove(window);
    windows.add(window);
  }

  void _enterFolder(DeskWindow window, String path, {required bool recordHistory}) {
    if (recordHistory) window.history.add(window.explorerPath);
    window.explorerPath = path;
    window.selectedName = null;
    window.title = _explorerTitle(path);
  }

  String _explorerTitle(String path) {
    if (path.isEmpty) return '${machine.workstation} - File Explorer';
    return '${_base(path)} - File Explorer';
  }

  String _notepadTitle(String path) => '${_base(path)} - Notepad';

  String _base(String path) {
    final parts = path.split('/').where((part) => part.isNotEmpty).toList();
    return parts.isEmpty ? machine.workstation : parts.last;
  }
}

class SessionScope extends InheritedWidget {
  const SessionScope({super.key, required this.session, required super.child});

  final Session session;

  static Session of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<SessionScope>();
    assert(scope != null, 'SessionScope is missing');
    return scope!.session;
  }

  @override
  bool updateShouldNotify(SessionScope oldWidget) => session != oldWidget.session;
}
