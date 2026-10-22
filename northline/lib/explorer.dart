import 'package:flutter/material.dart';
import 'package:northline/chrome.dart';
import 'package:northline/glyphs.dart';
import 'package:northline/session.dart';
import 'package:northline/theme.dart';
import 'package:northline/virtual_fs.dart';

class ExplorerView extends StatelessWidget {
  const ExplorerView({super.key, required this.session, required this.window});

  final Session session;
  final DeskWindow window;

  @override
  Widget build(BuildContext context) {
    final machine = session.machine;
    final items = session.fs.list(window.explorerPath);
    final places = [
      (machine.desktop, 'Desktop'),
      (machine.documents, 'Documents'),
      (machine.pictures, 'Pictures'),
    ];
    return ColoredBox(
      color: Colors.white,
      child: Column(
        children: [
          Container(
            height: 42,
            color: NorthlineColors.panel,
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(
              children: [
                _NavButton(
                  label: 'Back',
                  enabled: window.history.isNotEmpty,
                  onTap: () => session.explorerBack(window),
                  child: const _Arrow(left: true),
                ),
                const SizedBox(width: 4),
                _NavButton(
                  label: 'Up',
                  enabled: session.fs.parentPath(window.explorerPath) != null,
                  onTap: () => session.explorerUp(window),
                  child: const _Arrow(up: true),
                ),
                const SizedBox(width: 8),
                PropButton(
                  label: 'Open',
                  onPressed: window.selectedName == null ? null : () => session.openSelected(window),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Container(
                    height: 28,
                    alignment: Alignment.centerLeft,
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      border: Border.all(color: const Color(0xFFABABAB)),
                    ),
                    child: Text(
                      machine.displayPath(window.explorerPath),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13, color: NorthlineColors.ink),
                    ),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: Row(
              children: [
                Container(
                  width: 168,
                  color: const Color(0xFFF7F7F7),
                  child: ListView(
                    children: [
                      const Padding(
                        padding: EdgeInsets.fromLTRB(12, 10, 12, 4),
                        child: Text(
                          'Folders',
                          style: TextStyle(fontSize: 12, color: NorthlineColors.muted, fontWeight: FontWeight.w600),
                        ),
                      ),
                      for (final place in places)
                        _PlaceRow(
                          label: place.$2,
                          selected: window.explorerPath == place.$1,
                          onTap: () => session.explorerGo(window, place.$1),
                        ),
                    ],
                  ),
                ),
                const VerticalDivider(width: 1, color: NorthlineColors.line),
                Expanded(
                  child: Column(
                    children: [
                      const _Header(),
                      Expanded(
                        child: items.isEmpty
                            ? const Center(
                                child: Text(
                                  'This folder is empty',
                                  style: TextStyle(color: NorthlineColors.muted),
                                ),
                              )
                            : ListView.builder(
                                itemCount: items.length,
                                itemBuilder: (context, index) {
                                  final node = items[index];
                                  return _FileRow(
                                    node: node,
                                    selected: window.selectedName == node.name,
                                    onTap: () => session.selectExplorer(window, node.name),
                                    onOpen: () => session.openExplorerNode(window, node),
                                  );
                                },
                              ),
                      ),
                      Container(
                        height: 26,
                        alignment: Alignment.centerLeft,
                        padding: const EdgeInsets.symmetric(horizontal: 10),
                        color: NorthlineColors.panel,
                        child: Text(
                          '${items.length} item${items.length == 1 ? '' : 's'}',
                          style: const TextStyle(fontSize: 12, color: NorthlineColors.muted),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header();

  @override
  Widget build(BuildContext context) {
    return const ColoredBox(
      color: Color(0xFFF7F7F7),
      child: SizedBox(
        height: 28,
        child: Row(
          children: [
            SizedBox(width: 36),
            Expanded(child: Text('Name', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600))),
            SizedBox(
              width: 140,
              child: Text('Type', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
            ),
          ],
        ),
      ),
    );
  }
}

class _FileRow extends StatelessWidget {
  const _FileRow({
    required this.node,
    required this.selected,
    required this.onTap,
    required this.onOpen,
  });

  final FsNode node;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      onDoubleTap: onOpen,
      child: ColoredBox(
        color: selected ? NorthlineColors.selection : Colors.transparent,
        child: SizedBox(
          height: 32,
          child: Row(
            children: [
              const SizedBox(width: 8),
              AppGlyph(node.isDirectory ? AppKind.explorer : AppKind.notepad, size: 16),
              const SizedBox(width: 8),
              Expanded(
                child: Text(node.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)),
              ),
              SizedBox(
                width: 140,
                child: Text(
                  node.isDirectory
                      ? 'File folder'
                      : (node.name.toLowerCase().endsWith('.txt') ? 'Text document' : 'File'),
                  style: const TextStyle(fontSize: 13, color: NorthlineColors.muted),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PlaceRow extends StatelessWidget {
  const _PlaceRow({required this.label, required this.selected, required this.onTap});

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: ColoredBox(
        color: selected ? NorthlineColors.selection : Colors.transparent,
        child: SizedBox(
          height: 32,
          child: Row(
            children: [
              const SizedBox(width: 12),
              const AppGlyph(AppKind.explorer, size: 16),
              const SizedBox(width: 8),
              Text(label, style: const TextStyle(fontSize: 13)),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.label,
    required this.enabled,
    required this.onTap,
    required this.child,
  });

  final String label;
  final bool enabled;
  final VoidCallback onTap;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: label,
      enabled: enabled,
      child: GestureDetector(
        onTap: enabled ? onTap : null,
        child: Container(
          width: 28,
          height: 28,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: Colors.white,
            border: Border.all(color: const Color(0xFFABABAB)),
          ),
          child: Opacity(opacity: enabled ? 1 : 0.35, child: child),
        ),
      ),
    );
  }
}

class _Arrow extends StatelessWidget {
  const _Arrow({this.left = false, this.up = false});

  final bool left;
  final bool up;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: const Size(12, 12),
      painter: _ArrowPainter(left: left, up: up),
    );
  }
}

class _ArrowPainter extends CustomPainter {
  const _ArrowPainter({required this.left, required this.up});

  final bool left;
  final bool up;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = NorthlineColors.ink
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    final path = Path();
    if (up) {
      path
        ..moveTo(2, 8)
        ..lineTo(6, 3)
        ..lineTo(10, 8);
    } else if (left) {
      path
        ..moveTo(8, 2)
        ..lineTo(3, 6)
        ..lineTo(8, 10);
    }
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _ArrowPainter oldDelegate) {
    return oldDelegate.left != left || oldDelegate.up != up;
  }
}
