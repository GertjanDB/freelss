import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:northline/glyphs.dart';
import 'package:northline/session.dart';
import 'package:northline/theme.dart';
import 'package:northline/window.dart';

const double kTaskbarHeight = 40;

class DesktopShell extends StatelessWidget {
  const DesktopShell({super.key});

  @override
  Widget build(BuildContext context) {
    final session = SessionScope.of(context);
    return ListenableBuilder(
      listenable: session,
      builder: (context, _) {
        return Material(
          color: NorthlineColors.wallpaperTop,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final desktop = Size(
                constraints.maxWidth,
                math.max(0, constraints.maxHeight - kTaskbarHeight),
              );
              return Stack(
                children: [
                  Positioned(
                    left: 0,
                    top: 0,
                    right: 0,
                    bottom: kTaskbarHeight,
                    child: _Desk(session: session, desktop: desktop),
                  ),
                  Positioned(
                    left: 0,
                    right: 0,
                    bottom: 0,
                    height: kTaskbarHeight,
                    child: _Taskbar(session: session),
                  ),
                  if (session.startOpen)
                    Positioned(
                      left: 0,
                      bottom: kTaskbarHeight,
                      child: _StartMenu(session: session),
                    ),
                ],
              );
            },
          ),
        );
      },
    );
  }
}

class _Desk extends StatelessWidget {
  const _Desk({required this.session, required this.desktop});

  final Session session;
  final Size desktop;

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        const Positioned.fill(child: _Wallpaper()),
        GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: session.dismiss,
          child: const SizedBox.expand(),
        ),
        for (final icon in _deskIcons)
          Positioned(
            left: 8,
            top: icon.top,
            width: 104,
            child: _DesktopIcon(
              label: icon.label,
              selected: session.selectedIcon == icon.id,
              glyph: AppGlyph(icon.kind, size: 40),
              onTap: () => session.selectIcon(icon.id),
              onOpen: () => session.openIcon(icon.id),
            ),
          ),
        for (final window in session.windows)
          if (!window.minimized)
            WindowFrame(
              key: ValueKey(window.id),
              session: session,
              window: window,
              desktop: desktop,
            ),
        if (session.startOpen)
          Positioned.fill(
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: session.dismiss,
            ),
          ),
      ],
    );
  }
}

class _DeskIconSpec {
  const _DeskIconSpec(this.id, this.kind, this.label, this.top);

  final String id;
  final AppKind kind;
  final String label;
  final double top;
}

const List<_DeskIconSpec> _deskIcons = [
  _DeskIconSpec('explorer', AppKind.explorer, 'File Explorer', 8),
  _DeskIconSpec('notepad', AppKind.notepad, 'Notepad', 108),
  _DeskIconSpec('pnd', AppKind.pnd, 'Police National\nDatabase', 200),
];

class _DesktopIcon extends StatelessWidget {
  const _DesktopIcon({
    required this.label,
    required this.selected,
    required this.glyph,
    required this.onTap,
    required this.onOpen,
  });

  final String label;
  final bool selected;
  final Widget glyph;
  final VoidCallback onTap;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      onDoubleTap: onOpen,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: selected ? const Color(0x553A6F90) : Colors.transparent,
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(4, 6, 4, 6),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              glyph,
              const SizedBox(height: 4),
              Text(
                label,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 12,
                  height: 1.15,
                  shadows: [Shadow(color: Color(0xCC000000), blurRadius: 3)],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Wallpaper extends StatelessWidget {
  const _Wallpaper();

  @override
  Widget build(BuildContext context) {
    return const DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Color(0xFF143044),
            Color(0xFF2C5A6C),
            Color(0xFF7FA8AE),
            Color(0xFFD5E0D4),
          ],
          stops: [0, 0.42, 0.72, 1],
        ),
      ),
      child: CustomPaint(painter: _RidgePainter()),
    );
  }
}

class _RidgePainter extends CustomPainter {
  const _RidgePainter();

  @override
  void paint(Canvas canvas, Size size) {
    final horizon = size.height * 0.62;
    final ridge = Paint()
      ..color = const Color(0x66143044)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4
      ..strokeJoin = StrokeJoin.round;
    final path = Path()
      ..moveTo(0, horizon)
      ..lineTo(size.width * 0.16, horizon - 28)
      ..lineTo(size.width * 0.3, horizon - 10)
      ..lineTo(size.width * 0.48, horizon - 74)
      ..lineTo(size.width * 0.66, horizon - 16)
      ..lineTo(size.width * 0.82, horizon - 46)
      ..lineTo(size.width, horizon - 8);
    canvas.drawPath(path, ridge);
    final mark = Paint()
      ..color = const Color(0xAAE7F4F2)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..strokeJoin = StrokeJoin.round;
    final cx = size.width * 0.74;
    final cy = size.height * 0.24;
    canvas.drawPath(
      Path()
        ..moveTo(cx - 18, cy + 10)
        ..lineTo(cx, cy - 16)
        ..lineTo(cx + 18, cy + 10),
      mark,
    );
    canvas.drawLine(Offset(cx - 28, cy + 10), Offset(cx + 28, cy + 10), mark);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _Taskbar extends StatelessWidget {
  const _Taskbar({required this.session});

  final Session session;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: NorthlineColors.taskbar,
        border: Border(top: BorderSide(color: Color(0xFF2E2E2E))),
      ),
      child: Row(
        children: [
          _StartButton(session: session),
          const SizedBox(width: 4),
          Expanded(
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                for (final window in session.windows)
                  _TaskButton(
                    title: window.title,
                    active: session.isFocused(window),
                    minimized: window.minimized,
                    onTap: () => session.taskbarClick(window),
                  ),
              ],
            ),
          ),
          const _TrayClock(),
        ],
      ),
    );
  }
}

class _StartButton extends StatelessWidget {
  const _StartButton({required this.session});

  final Session session;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'Start',
      child: GestureDetector(
        onTap: session.toggleStart,
          child: ColoredBox(
          color: session.startOpen ? NorthlineColors.taskbarRaised : Colors.transparent,
          child: SizedBox(
            height: kTaskbarHeight,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const NorthlineMark(size: 16),
                  const SizedBox(width: 8),
                  Text(
                    session.machine.shortName,
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TaskButton extends StatelessWidget {
  const _TaskButton({
    required this.title,
    required this.active,
    required this.minimized,
    required this.onTap,
  });

  final String title;
  final bool active;
  final bool minimized;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 4),
      child: GestureDetector(
        onTap: onTap,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: active ? NorthlineColors.taskbarActive : const Color(0xFF2A2A2A),
            border: Border(
              bottom: BorderSide(
                color: active ? NorthlineColors.ice : Colors.transparent,
                width: 2,
              ),
            ),
          ),
          child: SizedBox(
            width: 168,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: minimized ? const Color(0xFFBDBDBD) : Colors.white,
                    fontSize: 12,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TrayClock extends StatefulWidget {
  const _TrayClock();

  @override
  State<_TrayClock> createState() => _TrayClockState();
}

class _TrayClockState extends State<_TrayClock> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    String two(int value) => value.toString().padLeft(2, '0');
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            '${two(now.hour)}:${two(now.minute)}',
            style: const TextStyle(color: Colors.white, fontSize: 12, height: 1.1),
          ),
          Text(
            '${two(now.day)}/${two(now.month)}/${now.year}',
            style: const TextStyle(color: Colors.white, fontSize: 11, height: 1.1),
          ),
        ],
      ),
    );
  }
}

class _StartMenu extends StatelessWidget {
  const _StartMenu({required this.session});

  final Session session;

  @override
  Widget build(BuildContext context) {
    final machine = session.machine;
    return Material(
      color: const Color(0xFF1C1C1C),
      elevation: 12,
        child: SizedBox(
        width: 360,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 16, 18, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    machine.osName,
                    style: const TextStyle(
                      color: NorthlineColors.ice,
                      fontSize: 12,
                      letterSpacing: 1.2,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    machine.fullName,
                    style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    machine.organization,
                    style: const TextStyle(color: Color(0xFFE4E4E4), fontSize: 14),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    'Workstation ${machine.workstation}',
                    style: const TextStyle(color: Color(0xFFA6A6A6), fontSize: 12),
                  ),
                ],
              ),
            ),
            const Divider(height: 1, color: Color(0xFF333333)),
            _StartApp(
              kind: AppKind.explorer,
              label: 'File Explorer',
              onTap: session.openExplorer,
            ),
            _StartApp(
              kind: AppKind.notepad,
              label: 'Notepad',
              onTap: session.openNotepad,
            ),
            _StartApp(
              kind: AppKind.pnd,
              label: 'Police National Database',
              onTap: session.openPnd,
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}

class _StartApp extends StatefulWidget {
  const _StartApp({required this.kind, required this.label, required this.onTap});

  final AppKind kind;
  final String label;
  final VoidCallback onTap;

  @override
  State<_StartApp> createState() => _StartAppState();
}

class _StartAppState extends State<_StartApp> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: ColoredBox(
          color: _hover ? const Color(0xFF2C2C2C) : Colors.transparent,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
            child: Row(
              children: [
                AppGlyph(widget.kind, size: 22),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    widget.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white, fontSize: 14),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
