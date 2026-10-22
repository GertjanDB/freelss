import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:northline/machine.dart';
import 'package:northline/session.dart';
import 'package:northline/shell.dart';
import 'package:northline/theme.dart';
import 'package:northline/virtual_fs.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    final raw = await rootBundle.loadString('config/machine.json');
    final machine = MachineConfig.parse(raw);
    runApp(NorthlineApp(session: Session(machine, VirtualFs(machine))));
  } catch (error) {
    runApp(
      MaterialApp(
        debugShowCheckedModeBanner: false,
        home: Scaffold(
          body: Center(child: Text('Could not read config/machine.json\n$error')),
        ),
      ),
    );
  }
}

class NorthlineApp extends StatelessWidget {
  const NorthlineApp({super.key, required this.session});

  final Session session;

  @override
  Widget build(BuildContext context) {
    return SessionScope(
      session: session,
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        title: session.machine.osName,
        theme: ThemeData(
          useMaterial3: false,
          fontFamily: 'Roboto',
          splashFactory: NoSplash.splashFactory,
          highlightColor: Colors.transparent,
          textSelectionTheme: const TextSelectionThemeData(
            cursorColor: NorthlineColors.navy,
            selectionColor: Color(0xFFB9D6EA),
          ),
        ),
        home: const DesktopShell(),
      ),
    );
  }
}
