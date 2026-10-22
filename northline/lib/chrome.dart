import 'package:flutter/material.dart';
import 'package:northline/theme.dart';

InputDecoration fieldDecoration(String hint) {
  const border = OutlineInputBorder(
    borderRadius: BorderRadius.zero,
    borderSide: BorderSide(color: Color(0xFF8A8A8A)),
  );
  return InputDecoration(
    isDense: true,
    hintText: hint,
    hintStyle: const TextStyle(color: Color(0xFF8A8A8A), fontSize: 14),
    filled: true,
    fillColor: Colors.white,
    contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
    border: border,
    enabledBorder: border,
    focusedBorder: const OutlineInputBorder(
      borderRadius: BorderRadius.zero,
      borderSide: BorderSide(color: NorthlineColors.navy, width: 1.4),
    ),
  );
}

class PropButton extends StatefulWidget {
  const PropButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.primary = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool primary;

  @override
  State<PropButton> createState() => _PropButtonState();
}

class _PropButtonState extends State<PropButton> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null;
    final primary = widget.primary && enabled;
    final Color background;
    final Color foreground;
    if (!enabled) {
      background = const Color(0xFFE6E6E6);
      foreground = const Color(0xFF8A8A8A);
    } else if (primary) {
      background = _hover ? const Color(0xFF2A5168) : NorthlineColors.navy;
      foreground = Colors.white;
    } else {
      background = _hover ? const Color(0xFFE9E9E9) : Colors.white;
      foreground = NorthlineColors.ink;
    }
    return MouseRegion(
      onEnter: enabled ? (_) => setState(() => _hover = true) : null,
      onExit: enabled ? (_) => setState(() => _hover = false) : null,
      child: GestureDetector(
        onTap: widget.onPressed,
        behavior: HitTestBehavior.opaque,
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: background,
            border: Border.all(color: primary ? background : const Color(0xFFADADAD)),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
            child: Text(widget.label, style: TextStyle(color: foreground, fontSize: 13)),
          ),
        ),
      ),
    );
  }
}
