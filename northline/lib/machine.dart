import 'dart:convert';

/// Identity for the one prop computer. Edit config/machine.json.
class MachineConfig {
  const MachineConfig({
    required this.osName,
    required this.fullName,
    required this.shortName,
    required this.organization,
    required this.workstation,
  });

  final String osName;
  final String fullName;
  final String shortName;
  final String organization;
  final String workstation;

  String get userRoot => '/Users/$fullName';
  String get desktop => '$userRoot/Desktop';
  String get documents => '$userRoot/Documents';
  String get pictures => '$userRoot/Pictures';

  /// Windows-style path, including the workstation name.
  String displayPath(String path) {
    if (path.isEmpty || path == '/') return '$workstation:\\';
    final normalized = path.startsWith('/') ? path : '/$path';
    return '$workstation:${normalized.replaceAll('/', r'\')}';
  }

  factory MachineConfig.fromJson(Map<String, dynamic> json) {
    String requiredText(String key) {
      final value = json[key];
      if (value is! String || value.trim().isEmpty) {
        throw FormatException('machine.json is missing "$key"');
      }
      return value;
    }

    return MachineConfig(
      osName: requiredText('osName'),
      fullName: requiredText('fullName'),
      shortName: requiredText('shortName'),
      organization: requiredText('organization'),
      workstation: requiredText('workstation'),
    );
  }

  static MachineConfig parse(String source) {
    return MachineConfig.fromJson(jsonDecode(source) as Map<String, dynamic>);
  }
}
