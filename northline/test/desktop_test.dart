import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:northline/machine.dart';
import 'package:northline/main.dart';
import 'package:northline/session.dart';
import 'package:northline/virtual_fs.dart';

Future<Session> _launch(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1440, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  const machine = MachineConfig(
    osName: 'Northline',
    fullName: 'Lauren Bell',
    shortName: 'L. Bell',
    organization: 'Bristol & County Police',
    workstation: 'BCP-WS01',
  );
  final session = Session(machine, VirtualFs(machine));
  await tester.pumpWidget(NorthlineApp(session: session));
  addTearDown(() async {
    await tester.pumpWidget(const SizedBox.shrink());
  });
  return session;
}

void main() {
  testWidgets('dragging the title bar moves the window', (tester) async {
    final session = await _launch(tester);
    session.openNotepad();
    await tester.pump();
    final before = session.windows.single.left;
    await tester.drag(find.byKey(const ValueKey('title-1')), const Offset(90, 24));
    await tester.pump();
    expect(session.windows.single.left, greaterThan(before + 40));
    expect(session.windows.single.minimized, isFalse);
    await tester.pump(const Duration(milliseconds: 400));
  });

  testWidgets('start menu shows the force and the full name', (tester) async {
    final session = await _launch(tester);
    expect(find.text('L. Bell'), findsOneWidget);
    session.toggleStart();
    await tester.pump();
    expect(find.text('Lauren Bell'), findsOneWidget);
    expect(find.text('Bristol & County Police'), findsOneWidget);
    expect(find.textContaining('BCP-WS01'), findsOneWidget);
    expect(find.text('Northline'), findsOneWidget);
  });

  testWidgets('notepad, explorer, minimize, and restore share one computer', (tester) async {
    final session = await _launch(tester);
    session.openNotepad();
    await tester.pump();
    await tester.enterText(find.byKey(const ValueKey('notepad-body')), 'Quay is quiet.');
    await tester.tap(find.text('Save'));
    await tester.pump();
    await tester.enterText(find.byKey(const ValueKey('save-name')), 'Watch');
    await tester.tap(find.text('Save').last);
    await tester.pump();

    expect(find.text('Watch.txt - Notepad'), findsNWidgets(2));
    final note = session.windows.single;
    session.taskbarClick(note);
    await tester.pump();
    expect(note.minimized, isTrue);
    expect(find.text('Watch.txt - Notepad'), findsOneWidget);
    session.taskbarClick(note);
    await tester.pump();
    expect(note.minimized, isFalse);

    session.openExplorer();
    await tester.pump();
    expect(find.textContaining(r'BCP-WS01:\Users\Lauren Bell\Documents'), findsWidgets);
    expect(find.text('Watch.txt'), findsOneWidget);
    note.text!.text = 'changed';
    await tester.tap(find.text('Watch.txt'));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Open'));
    await tester.pump();
    expect(note.text!.text, 'Quay is quiet.');
  });

  testWidgets('PND search, record, and save show up in Explorer', (tester) async {
    final session = await _launch(tester);
    session.openPnd();
    await tester.pump();
    expect(find.text('Bristol & County Police'), findsOneWidget);
    expect(find.text('Lauren Bell'), findsOneWidget);
    expect(find.text('Police National Database - L. Bell'), findsWidgets);

    await tester.enterText(find.byKey(const ValueKey('pnd-search')), 'Ellison');
    await tester.pump();
    await tester.tap(find.text('Mara Ellison'));
    await tester.pump();
    expect(find.text('Warning'), findsOneWidget);
    expect(find.textContaining('INC-4418'), findsOneWidget);
    expect(find.text('NO PHOTOGRAPH'), findsOneWidget);

    await tester.tap(find.text('NL07 HCM  Hartley Comet'));
    await tester.pump();
    expect(find.text('Stolen'), findsNothing);
    expect(find.text('Seen at scene'), findsOneWidget);
    expect(find.text('NL07 HCM'), findsWidgets);

    await tester.tap(find.text('Save record'));
    await tester.pump();
    await tester.tap(find.text('Save search'));
    await tester.pump();

    session.openExplorer();
    await tester.pump();
    expect(find.text('PND Hartley Comet.txt'), findsOneWidget);
    expect(find.text('PND search Ellison.txt'), findsOneWidget);
  });
}
