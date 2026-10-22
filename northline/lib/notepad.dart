import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:northline/chrome.dart';
import 'package:northline/session.dart';
import 'package:northline/theme.dart';

class NotepadView extends StatelessWidget {
  const NotepadView({super.key, required this.session, required this.window});

  final Session session;
  final DeskWindow window;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Column(
          children: [
            Container(
              height: 40,
              color: NorthlineColors.panel,
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Row(
                children: [
                  PropButton(label: 'Save', onPressed: () => session.saveNotepad(window)),
                  const SizedBox(width: 6),
                  PropButton(label: 'Save as', onPressed: () => session.beginSaveAs(window)),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      window.status ?? '',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12, color: NorthlineColors.muted),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: CallbackShortcuts(
                bindings: {
                  const SingleActivator(LogicalKeyboardKey.keyS, control: true): () => session.saveNotepad(window),
                },
                child: TextField(
                  key: const ValueKey('notepad-body'),
                  controller: window.text,
                  expands: true,
                  maxLines: null,
                  textAlignVertical: TextAlignVertical.top,
                  spellCheckConfiguration: const SpellCheckConfiguration.disabled(),
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 14,
                    height: 1.4,
                    color: NorthlineColors.ink,
                  ),
                  decoration: const InputDecoration(
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.all(12),
                  ),
                ),
              ),
            ),
          ],
        ),
        if (window.showSaveAs) _SaveAs(session: session, window: window),
      ],
    );
  }
}

class _SaveAs extends StatelessWidget {
  const _SaveAs({required this.session, required this.window});

  final Session session;
  final DeskWindow window;

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: ColoredBox(
        color: const Color(0x66000000),
        child: Center(
          child: Material(
            color: Colors.white,
            child: SizedBox(
              width: 380,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text('Save as', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    Text(
                      session.machine.displayPath(session.machine.documents),
                      style: const TextStyle(fontSize: 12, color: NorthlineColors.muted),
                    ),
                    const SizedBox(height: 12),
                    const Text('File name', style: TextStyle(fontSize: 12)),
                    const SizedBox(height: 4),
                    TextField(
                      key: const ValueKey('save-name'),
                      controller: window.saveName,
                      autofocus: true,
                      spellCheckConfiguration: const SpellCheckConfiguration.disabled(),
                      decoration: fieldDecoration('Notes.txt'),
                    ),
                    const SizedBox(height: 14),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        PropButton(label: 'Cancel', onPressed: () => session.cancelSaveAs(window)),
                        const SizedBox(width: 8),
                        PropButton(
                          label: 'Save',
                          primary: true,
                          onPressed: () => session.commitSaveAs(window),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
