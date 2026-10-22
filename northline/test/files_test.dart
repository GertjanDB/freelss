import 'package:flutter_test/flutter_test.dart';
import 'package:northline/machine.dart';
import 'package:northline/pnd_data.dart';
import 'package:northline/session.dart';
import 'package:northline/virtual_fs.dart';

MachineConfig get _machine => const MachineConfig(
  osName: 'Northline',
  fullName: 'Lauren Bell',
  shortName: 'L. Bell',
  organization: 'Bristol & County Police',
  workstation: 'BCP-WS01',
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('a note saved in Notepad is readable from the shared files', () {
    final session = Session(_machine, VirtualFs(_machine));
    final note = session.openNotepad();
    note.text!.text = 'Quay is quiet.';
    session.beginSaveAs(note);
    note.saveName!.text = 'Watch';
    session.commitSaveAs(note);

    final names = session.fs.list(_machine.documents).map((node) => node.name);
    expect(names, contains('Watch.txt'));
    final again = session.openNotepad(path: '${_machine.documents}/Watch.txt');
    expect(again.text!.text, 'Quay is quiet.');
    expect(session.fs.read('${_machine.documents}/Field Notes.txt'), contains('Lauren Bell'));
    session.close(note);
  });

  test('PND search finds people and vehicles', () {
    expect(filterRecords('Pike').map((record) => record.id), ['person-pike']);
    expect(filterRecords('stolen').single.id, 'vehicle-kst');
    expect(
      filterRecords('Ellison').map((record) => record.id),
      containsAll(['person-ellison', 'vehicle-hcm']),
    );
  });

  test('saving a PND record writes a file Explorer can open', () {
    final session = Session(_machine, VirtualFs(_machine));
    final window = session.openPnd();
    window.pndSelectedId = 'person-ellison';
    session.savePndRecord(window);
    window.pndQuery!.text = 'Ellison';
    session.savePndSearch(window);

    final recordPath = '${_machine.documents}/PND Mara Ellison.txt';
    final searchPath = '${_machine.documents}/PND search Ellison.txt';
    final record = session.fs.read(recordPath);
    expect(record, contains('Officer: Lauren Bell'));
    expect(record, contains('Force: Bristol & County Police'));
    expect(record, contains('Workstation: BCP-WS01'));
    expect(record, contains('INC-4418'));
    expect(record, contains('Warning'));
    expect(session.fs.read(searchPath), contains('Mara Ellison'));

    final opened = session.openNotepad(path: recordPath);
    expect(opened.text!.text, contains('NL07 HCM'));
    session.close(window);
    session.close(opened);
  });
}
