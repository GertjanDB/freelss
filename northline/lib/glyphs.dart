import 'package:flutter/material.dart';
import 'package:northline/session.dart';
import 'package:northline/theme.dart';

class AppGlyph extends StatelessWidget {
  const AppGlyph(this.kind, {super.key, this.size = 32});

  final AppKind kind;
  final double size;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size.square(size),
      painter: switch (kind) {
        AppKind.explorer => const _FolderPainter(),
        AppKind.notepad => const _PagePainter(),
        AppKind.pnd => const _RecordPainter(),
      },
    );
  }
}

class NorthlineMark extends StatelessWidget {
  const NorthlineMark({super.key, this.size = 16, this.color = NorthlineColors.ice});

  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size.square(size),
      painter: _MarkPainter(color),
    );
  }
}

class _FolderPainter extends CustomPainter {
  const _FolderPainter();

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 32);
    final tab = RRect.fromRectAndRadius(const Rect.fromLTWH(3, 6, 12, 6), const Radius.circular(1.5));
    final body = RRect.fromRectAndRadius(const Rect.fromLTWH(3, 10, 26, 16), const Radius.circular(2));
    canvas.drawRRect(tab, Paint()..color = const Color(0xFF24586E));
    canvas.drawRRect(body, Paint()..color = NorthlineColors.lake);
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _PagePainter extends CustomPainter {
  const _PagePainter();

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 32);
    canvas.drawRRect(
      RRect.fromRectAndRadius(const Rect.fromLTWH(7, 3, 18, 26), const Radius.circular(1.5)),
      Paint()..color = const Color(0xFFF7F4EC),
    );
    canvas.drawRect(const Rect.fromLTWH(7, 3, 3, 26), Paint()..color = NorthlineColors.lake);
    final line = Paint()
      ..color = const Color(0xFF8AA0AE)
      ..strokeWidth = 1.2;
    for (final y in [10.0, 14.0, 18.0, 22.0]) {
      canvas.drawLine(Offset(12, y), Offset(22, y), line);
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _RecordPainter extends CustomPainter {
  const _RecordPainter();

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 32);
    canvas.drawRRect(
      RRect.fromRectAndRadius(const Rect.fromLTWH(4, 4, 24, 24), const Radius.circular(2)),
      Paint()..color = const Color(0xFFF4F7F8),
    );
    canvas.drawRect(const Rect.fromLTWH(4, 4, 24, 7), Paint()..color = NorthlineColors.navy);
    canvas.drawCircle(const Offset(11, 18), 3, Paint()..color = NorthlineColors.lake);
    final ink = Paint()
      ..color = NorthlineColors.navy
      ..strokeWidth = 1.4
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(const Offset(16, 16), const Offset(24, 16), ink);
    canvas.drawLine(
      const Offset(16, 20),
      const Offset(22, 20),
      Paint()
        ..color = const Color(0xFF8AA0AE)
        ..strokeWidth = 1.4
        ..strokeCap = StrokeCap.round,
    );
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _MarkPainter extends CustomPainter {
  const _MarkPainter(this.color);

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.save();
    canvas.scale(size.width / 16);
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    canvas.drawLine(const Offset(1, 12), const Offset(15, 12), paint);
    canvas.drawPath(Path()..moveTo(3, 12)..lineTo(8, 4)..lineTo(13, 12), paint);
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _MarkPainter oldDelegate) => oldDelegate.color != color;
}

class CaptionIcon extends StatelessWidget {
  const CaptionIcon(this.kind, {super.key, this.color = NorthlineColors.ink});

  final CaptionKind kind;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: const Size.square(10),
      painter: _CaptionPainter(kind, color),
    );
  }
}

enum CaptionKind { minimize, maximize, restore, close }

class _CaptionPainter extends CustomPainter {
  const _CaptionPainter(this.kind, this.color);

  final CaptionKind kind;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.1
      ..strokeCap = StrokeCap.square;
    switch (kind) {
      case CaptionKind.minimize:
        canvas.drawLine(Offset(0, size.height - 1), Offset(size.width, size.height - 1), paint);
      case CaptionKind.maximize:
        canvas.drawRect(Rect.fromLTWH(0.5, 0.5, size.width - 1, size.height - 1), paint);
      case CaptionKind.restore:
        canvas.drawRect(Rect.fromLTWH(2.2, 0.5, 7, 7), paint);
        canvas.drawRect(Rect.fromLTWH(0.5, 2.5, 7, 7), paint);
      case CaptionKind.close:
        canvas.drawLine(const Offset(0, 0), Offset(size.width, size.height), paint);
        canvas.drawLine(Offset(0, size.height), Offset(size.width, 0), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _CaptionPainter oldDelegate) {
    return oldDelegate.kind != kind || oldDelegate.color != color;
  }
}
