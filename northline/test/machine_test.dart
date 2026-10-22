import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:northline/machine.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('machine.json is the only identity', () async {
    final config = MachineConfig.parse(await rootBundle.loadString('config/machine.json'));
    expect(config.osName, 'Northline');
    expect(config.fullName, 'Lauren Bell');
    expect(config.shortName, 'L. Bell');
    expect(config.organization, 'Bristol & County Police');
    expect(config.workstation, 'BCP-WS01');
    expect(
      config.displayPath(config.documents),
      r'BCP-WS01:\Users\Lauren Bell\Documents',
    );
  });
}
