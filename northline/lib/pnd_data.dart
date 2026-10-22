import 'package:northline/machine.dart';

/// Fictional prop records. Not a live system and not real people.
enum PndKind { person, vehicle }

class PndIncident {
  const PndIncident({required this.ref, required this.date, required this.title});

  final String ref;
  final String date;
  final String title;
}

class PndRecord {
  const PndRecord({
    required this.id,
    required this.kind,
    required this.name,
    this.born = '',
    this.address = '',
    this.registration = '',
    this.detail = '',
    this.markers = const [],
    this.incidents = const [],
    this.linkedIds = const [],
  });

  final String id;
  final PndKind kind;
  final String name;
  final String born;
  final String address;
  final String registration;
  final String detail;
  final List<String> markers;
  final List<PndIncident> incidents;
  final List<String> linkedIds;

  String get kindLabel => kind == PndKind.person ? 'Person' : 'Vehicle';

  String get initials {
    final parts = name.split(' ').where((part) => part.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    if (parts.length == 1) return parts.first[0].toUpperCase();
    return '${parts.first[0]}${parts.last[0]}'.toUpperCase();
  }
}

const List<PndRecord> pndRecords = [
  PndRecord(
    id: 'person-ellison',
    kind: PndKind.person,
    name: 'Mara Ellison',
    born: '12/04/1986',
    address: '14 Lantern Walk, Harrowcombe',
    markers: ['Warning'],
    incidents: [
      PndIncident(
        ref: 'INC-4418',
        date: '02/10/2026',
        title: 'Front door forced, Lantern Walk',
      ),
    ],
    linkedIds: ['vehicle-hcm'],
  ),
  PndRecord(
    id: 'vehicle-hcm',
    kind: PndKind.vehicle,
    name: 'Hartley Comet',
    registration: 'NL07 HCM',
    detail: '2014 grey hatchback',
    markers: ['Seen at scene'],
    incidents: [
      PndIncident(
        ref: 'INC-4418',
        date: '02/10/2026',
        title: 'Front door forced, Lantern Walk',
      ),
    ],
    linkedIds: ['person-ellison'],
  ),
  PndRecord(
    id: 'person-pike',
    kind: PndKind.person,
    name: 'Owen Pike',
    born: '03/11/1991',
    address: '8 Canal Cottages, Kestleford',
    markers: ['Missing'],
    incidents: [
      PndIncident(
        ref: 'INC-4390',
        date: '28/09/2026',
        title: 'Did not return to the hostel',
      ),
    ],
  ),
  PndRecord(
    id: 'person-crowe',
    kind: PndKind.person,
    name: 'Helen Crowe',
    born: '19/06/1978',
    address: '2 Wharf Office, Kestleford Quay',
    markers: ['Victim'],
    incidents: [
      PndIncident(
        ref: 'INC-4377',
        date: '21/09/2026',
        title: 'Estate taken from the quay car park',
      ),
    ],
    linkedIds: ['vehicle-kst'],
  ),
  PndRecord(
    id: 'vehicle-kst',
    kind: PndKind.vehicle,
    name: 'Calder Estate',
    registration: 'NL07 KST',
    detail: '2017 dark estate',
    markers: ['Stolen'],
    incidents: [
      PndIncident(
        ref: 'INC-4377',
        date: '21/09/2026',
        title: 'Estate taken from the quay car park',
      ),
    ],
    linkedIds: ['person-crowe'],
  ),
];

final Map<String, PndRecord> pndById = {
  for (final record in pndRecords) record.id: record,
};

PndRecord? recordById(String id) => pndById[id];

List<PndRecord> filterRecords(String query) {
  final trimmed = query.trim().toLowerCase();
  if (trimmed.isEmpty) return pndRecords;
  return pndRecords.where((record) => _matches(record, trimmed)).toList();
}

bool _matches(PndRecord record, String query) {
  final raw = _haystack(record);
  if (raw.contains(query)) return true;
  final compactQuery = query.replaceAll(' ', '');
  return compactQuery.isNotEmpty && raw.replaceAll(' ', '').contains(compactQuery);
}

String _haystack(PndRecord record) {
  final linked = [
    for (final id in record.linkedIds)
      if (recordById(id) case final item?) '${item.name} ${item.registration}',
  ];
  return [
    record.name,
    record.kindLabel,
    record.born,
    record.address,
    record.registration,
    record.detail,
    ...record.markers,
    for (final incident in record.incidents) '${incident.ref} ${incident.date} ${incident.title}',
    ...linked,
  ].join(' ').toLowerCase();
}

String recordFileName(PndRecord record) => 'PND ${_safe(record.name)}.txt';

String searchFileName(String query) {
  final label = _safe(query.trim());
  return 'PND search ${label.isEmpty ? 'all' : label}.txt';
}

String recordFileText(PndRecord record, MachineConfig machine) {
  final buffer = StringBuffer()
    ..writeln('Northline / Police National Database')
    ..writeln('Force: ${machine.organization}')
    ..writeln('Officer: ${machine.fullName}')
    ..writeln('Workstation: ${machine.workstation}')
    ..writeln()
    ..writeln('Type: ${record.kindLabel}')
    ..writeln('Name: ${record.name}');
  if (record.kind == PndKind.person) {
    buffer
      ..writeln('Born: ${record.born}')
      ..writeln('Address: ${record.address}');
  } else {
    buffer
      ..writeln('Registration: ${record.registration}')
      ..writeln('Description: ${record.detail}');
  }
  buffer
    ..writeln('Markers: ${record.markers.join(', ')}')
    ..writeln()
    ..writeln('Linked incidents:');
  for (final incident in record.incidents) {
    buffer.writeln('${incident.ref}  ${incident.date}  ${incident.title}');
  }
  buffer
    ..writeln()
    ..writeln('Linked records:');
  for (final id in record.linkedIds) {
    final item = recordById(id);
    if (item == null) continue;
    if (item.kind == PndKind.vehicle) {
      buffer.writeln('${item.registration}  ${item.name}');
    } else {
      buffer.writeln(item.name);
    }
  }
  return buffer.toString().trimRight();
}

String searchFileText(String query, List<PndRecord> results, MachineConfig machine) {
  final buffer = StringBuffer()
    ..writeln('Northline / Police National Database')
    ..writeln('Force: ${machine.organization}')
    ..writeln('Officer: ${machine.fullName}')
    ..writeln('Workstation: ${machine.workstation}')
    ..writeln()
    ..writeln('Search: ${query.trim().isEmpty ? '(all records)' : query.trim()}')
    ..writeln('Results: ${results.length}')
    ..writeln();
  for (final record in results) {
    final extra = record.kind == PndKind.vehicle ? record.registration : record.address;
    buffer.writeln('${record.name} — ${record.kindLabel} — $extra');
  }
  return buffer.toString().trimRight();
}

String _safe(String value) {
  final cleaned = value.replaceAll(RegExp(r'[\\/:*?"<>|]'), '').trim();
  return cleaned.isEmpty ? 'record' : cleaned;
}
