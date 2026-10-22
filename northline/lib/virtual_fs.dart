import 'package:northline/machine.dart';

class FsNode {
  FsNode.dir(this.name) : isDirectory = true, content = '';
  FsNode.file(this.name, this.content) : isDirectory = false;

  final String name;
  final bool isDirectory;
  String content;
  final List<FsNode> children = [];
  FsNode? parent;

  String get path {
    if (parent == null) return '';
    final parts = <String>[];
    FsNode? node = this;
    while (node?.parent != null) {
      parts.add(node!.name);
      node = node.parent;
    }
    return '/${parts.reversed.join('/')}';
  }
}

/// In-memory files shared by every program on this computer.
class VirtualFs {
  VirtualFs(MachineConfig machine) {
    root = FsNode.dir('');
    final users = _mkdir(root, 'Users');
    final user = _mkdir(users, machine.fullName);
    _mkdir(user, 'Desktop');
    final documents = _mkdir(user, 'Documents');
    _mkdir(user, 'Pictures');
    _touch(
      documents,
      'Field Notes.txt',
      'Northline field note\n'
      'Workstation: ${machine.workstation}\n'
      'User: ${machine.fullName}\n'
      'Force: ${machine.organization}\n'
      '\n'
      'Saved notes and database extracts go in Documents.\n',
    );
  }

  late final FsNode root;

  FsNode resolve(String path) {
    if (path.isEmpty || path == '/') return root;
    var node = root;
    for (final part in _parts(path)) {
      final next = node.children.where((child) => child.name == part).firstOrNull;
      if (next == null) {
        throw StateError('No such path: $path');
      }
      node = next;
    }
    return node;
  }

  List<FsNode> list(String path) {
    final children = [...resolve(path).children];
    children.sort((a, b) {
      if (a.isDirectory != b.isDirectory) return a.isDirectory ? -1 : 1;
      return a.name.toLowerCase().compareTo(b.name.toLowerCase());
    });
    return children;
  }

  String read(String path) {
    final node = resolve(path);
    if (node.isDirectory) throw StateError('Not a file: $path');
    return node.content;
  }

  String? parentPath(String path) {
    if (path.isEmpty || path == '/') return null;
    return resolve(path).parent?.path;
  }

  void writeFile(String path, String content) {
    final parts = _parts(path);
    if (parts.isEmpty) throw ArgumentError('empty path');
    var directory = root;
    for (final part in parts.sublist(0, parts.length - 1)) {
      final existing = directory.children
          .where((child) => child.isDirectory && child.name == part)
          .firstOrNull;
      directory = existing ?? _mkdir(directory, part);
    }
    final name = parts.last;
    final existing = directory.children
        .where((child) => !child.isDirectory && child.name == name)
        .firstOrNull;
    if (existing != null) {
      existing.content = content;
      return;
    }
    _touch(directory, name, content);
  }

  FsNode _mkdir(FsNode parent, String name) {
    final node = FsNode.dir(name)..parent = parent;
    parent.children.add(node);
    return node;
  }

  void _touch(FsNode parent, String name, String content) {
    parent.children.add(FsNode.file(name, content)..parent = parent);
  }

  List<String> _parts(String path) {
    return path.split('/').where((part) => part.isNotEmpty).toList();
  }
}
