import 'package:flutter/material.dart';
import 'package:northline/explorer.dart';
import 'package:northline/glyphs.dart';
import 'package:northline/notepad.dart';
import 'package:northline/pnd.dart';
import 'package:northline/session.dart';
import 'package:northline/theme.dart';

class WindowFrame extends StatelessWidget {
  const WindowFrame({
    super.key,
    required this.session,
    required this.window,
    required this.desktop,
  });

  final Session session;
  final DeskWindow window;
  final Size desktop;

  @override
  Widget build(BuildContext context) {
    final active = session.isFocused(window);
    final rect = window.maximized
        ? Rect.fromLTWH(0, 0, desktop.width, desktop.height)
        : Rect.fromLTWH(window.left, window.top, window.width, window.height);
    return Positioned(
      left: rect.left,
      top: rect.top,
      width: rect.width,
      height: rect.height,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(color: const Color(0xFF8A8A8A)),
          boxShadow: [
            BoxShadow(
              color: const Color(0x59000000),
              blurRadius: active ? 16 : 6,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Material(
          type: MaterialType.transparency,
          child: Stack(
            children: [
              Column(
                children: [
                  _TitleBar(session: session, window: window, active: active, desktop: desktop),
                  Expanded(
                    child: Listener(
                      onPointerDown: (_) => session.focus(window),
                      child: switch (window.kind) {
                        AppKind.explorer => ExplorerView(session: session, window: window),
                        AppKind.notepad => NotepadView(session: session, window: window),
                        AppKind.pnd => PndView(session: session, window: window),
                      },
                    ),
                  ),
                ],
              ),
              if (!window.maximized) ..._handles(),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _handles() {
    Widget handle(WindowEdge edge, MouseCursor cursor) {
      return MouseRegion(
        cursor: cursor,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onPanUpdate: (details) => session.resize(window, edge, details.delta, desktop),
        ),
      );
    }

    return [
      Positioned(top: 12, bottom: 12, left: 0, width: 6, child: handle(WindowEdge.west, SystemMouseCursors.resizeLeftRight)),
      Positioned(top: 12, bottom: 12, right: 0, width: 6, child: handle(WindowEdge.east, SystemMouseCursors.resizeLeftRight)),
      Positioned(left: 12, right: 12, top: 0, height: 5, child: handle(WindowEdge.north, SystemMouseCursors.resizeUpDown)),
      Positioned(left: 12, right: 12, bottom: 0, height: 6, child: handle(WindowEdge.south, SystemMouseCursors.resizeUpDown)),
      Positioned(left: 0, top: 0, width: 12, height: 12, child: handle(WindowEdge.northWest, SystemMouseCursors.resizeUpLeftDownRight)),
      Positioned(right: 0, top: 0, width: 12, height: 12, child: handle(WindowEdge.northEast, SystemMouseCursors.resizeUpRightDownLeft)),
      Positioned(left: 0, bottom: 0, width: 14, height: 14, child: handle(WindowEdge.southWest, SystemMouseCursors.resizeUpRightDownLeft)),
      Positioned(right: 0, bottom: 0, width: 14, height: 14, child: handle(WindowEdge.southEast, SystemMouseCursors.resizeUpLeftDownRight)),
    ];
  }
}

class _TitleBar extends StatelessWidget {
  const _TitleBar({
    required this.session,
    required this.window,
    required this.active,
    required this.desktop,
  });

  final Session session;
  final DeskWindow window;
  final bool active;
  final Size desktop;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: active ? Colors.white : const Color(0xFFF3F3F3),
      child: SizedBox(
        height: 32,
        child: Row(
          children: [
            const SizedBox(width: 8),
            AppGlyph(window.kind, size: 16),
            const SizedBox(width: 8),
            Expanded(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => session.focus(window),
                onDoubleTap: () => session.toggleMax(window),
                onPanUpdate: window.maximized
                    ? null
                    : (details) {
                        session.focus(window);
                        session.moveBy(window, details.delta, desktop);
                      },
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    window.title,
                    key: ValueKey('title-${window.id}'),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: active ? NorthlineColors.ink : const Color(0xFF6A6A6A),
                      fontSize: 12,
                    ),
                  ),
                ),
              ),
            ),
            _CaptionButton(
              kind: CaptionKind.minimize,
              label: 'Minimize',
              onTap: () => session.minimize(window),
            ),
            _CaptionButton(
              kind: window.maximized ? CaptionKind.restore : CaptionKind.maximize,
              label: window.maximized ? 'Restore' : 'Maximize',
              onTap: () => session.toggleMax(window),
            ),
            _CaptionButton(
              kind: CaptionKind.close,
              label: 'Close',
              danger: true,
              onTap: () => session.close(window),
            ),
          ],
        ),
      ),
    );
  }
}

class _CaptionButton extends StatefulWidget {
  const _CaptionButton({
    required this.kind,
    required this.label,
    required this.onTap,
    this.danger = false,
  });

  final CaptionKind kind;
  final String label;
  final VoidCallback onTap;
  final bool danger;

  @override
  State<_CaptionButton> createState() => _CaptionButtonState();
}

class _CaptionButtonState extends State<_CaptionButton> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final background = _hover
        ? (widget.danger ? NorthlineColors.close : const Color(0xFFE5E5E5))
        : Colors.transparent;
    final color = _hover && widget.danger ? Colors.white : NorthlineColors.ink;
    return Semantics(
      button: true,
      label: widget.label,
      child: MouseRegion(
        onEnter: (_) => setState(() => _hover = true),
        onExit: (_) => setState(() => _hover = false),
        child: GestureDetector(
          onTap: widget.onTap,
          child: ColoredBox(
            color: background,
            child: SizedBox(
              width: 46,
              height: 32,
              child: Center(child: CaptionIcon(widget.kind, color: color)),
            ),
          ),
        ),
      ),
    );
  }
}
