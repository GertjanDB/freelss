import 'package:flutter/material.dart';
import 'package:northline/chrome.dart';
import 'package:northline/pnd_data.dart';
import 'package:northline/session.dart';
import 'package:northline/theme.dart';

class PndView extends StatefulWidget {
  const PndView({super.key, required this.session, required this.window});

  final Session session;
  final DeskWindow window;

  @override
  State<PndView> createState() => _PndViewState();
}

class _PndViewState extends State<PndView> {
  void _select(String id) {
    widget.window.pndSelectedId = id;
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final session = widget.session;
    final window = widget.window;
    final machine = session.machine;
    final query = window.pndQuery?.text ?? '';
    final results = filterRecords(query);
    final selected = recordById(window.pndSelectedId ?? '');
    return ColoredBox(
      color: const Color(0xFFF7F9FA),
      child: Column(
        children: [
          _Header(machineName: machine.organization, officer: machine.fullName, shortOfficer: machine.shortName, workstation: machine.workstation),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Search',
                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: NorthlineColors.navy),
                      ),
                      const SizedBox(height: 4),
                      TextField(
                        key: const ValueKey('pnd-search'),
                        controller: window.pndQuery,
                        spellCheckConfiguration: const SpellCheckConfiguration.disabled(),
                        decoration: fieldDecoration('Name, vehicle, or incident'),
                        onChanged: (_) => setState(() {}),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                PropButton(label: 'Save search', onPressed: () => session.savePndSearch(window)),
              ],
            ),
          ),
          Expanded(
            child: Row(
              children: [
                SizedBox(
                  width: 250,
                  child: ColoredBox(
                    color: Colors.white,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Padding(
                          padding: const EdgeInsets.fromLTRB(12, 8, 12, 6),
                          child: Text(
                            'Results (${results.length})',
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: NorthlineColors.navy),
                          ),
                        ),
                        const Divider(height: 1, color: NorthlineColors.line),
                        Expanded(
                          child: results.isEmpty
                              ? const Padding(
                                  padding: EdgeInsets.all(12),
                                  child: Text('No records match this search.', style: TextStyle(color: NorthlineColors.muted)),
                                )
                              : ListView.builder(
                                  itemCount: results.length,
                                  itemBuilder: (context, index) {
                                    final record = results[index];
                                    final isSelected = record.id == window.pndSelectedId;
                                    return GestureDetector(
                                      onTap: () => _select(record.id),
                                      child: ColoredBox(
                                        color: isSelected ? NorthlineColors.selection : Colors.transparent,
                                        child: Padding(
                                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Text(record.name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                                              Text(
                                                record.kind == PndKind.vehicle
                                                    ? 'Vehicle  ${record.registration}'
                                                    : 'Person',
                                                style: const TextStyle(fontSize: 12, color: NorthlineColors.muted),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    );
                                  },
                                ),
                        ),
                      ],
                    ),
                  ),
                ),
                const VerticalDivider(width: 1, color: NorthlineColors.line),
                Expanded(
                  child: selected == null
                      ? const Center(
                          child: Text(
                            'Select a record',
                            style: TextStyle(color: NorthlineColors.muted, fontSize: 14),
                          ),
                        )
                      : _Detail(
                          record: selected,
                          onSelect: _select,
                          onSave: () => session.savePndRecord(window),
                        ),
                ),
              ],
            ),
          ),
          Container(
            height: 28,
            alignment: Alignment.centerLeft,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            color: NorthlineColors.panel,
            child: Text(
              window.status ?? '${results.length} records',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 12, color: NorthlineColors.muted),
            ),
          ),
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.machineName,
    required this.officer,
    required this.shortOfficer,
    required this.workstation,
  });

  final String machineName;
  final String officer;
  final String shortOfficer;
  final String workstation;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: NorthlineColors.navy, width: 3)),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 640;
            return Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        machineName,
                        style: const TextStyle(
                          color: NorthlineColors.navy,
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const Text(
                        'Police National Database',
                        style: TextStyle(color: NorthlineColors.ink, fontSize: 13),
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    const Text(
                      'Signed in',
                      style: TextStyle(fontSize: 10, color: NorthlineColors.muted, letterSpacing: 0.4),
                    ),
                    Text(
                      compact ? shortOfficer : officer,
                      style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: NorthlineColors.ink),
                    ),
                    Text(workstation, style: const TextStyle(fontSize: 12, color: NorthlineColors.muted)),
                  ],
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _Detail extends StatelessWidget {
  const _Detail({required this.record, required this.onSelect, required this.onSave});

  final PndRecord record;
  final ValueChanged<String> onSelect;
  final VoidCallback onSave;

  @override
  Widget build(BuildContext context) {
    final fields = record.kind == PndKind.person
        ? [
            _Field('Born', record.born),
            _Field('Address', record.address),
          ]
        : [
            _Field('Registration', record.registration),
            _Field('Description', record.detail),
          ];
    final linked = [
      for (final id in record.linkedIds) ?recordById(id),
    ];
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _PhotoPlaceholder(vehicle: record.kind == PndKind.vehicle, initials: record.initials),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      record.kindLabel,
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: NorthlineColors.navy),
                    ),
                    Text(record.name, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    for (final field in fields)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            SizedBox(
                              width: 110,
                              child: Text(field.label, style: const TextStyle(fontSize: 13, color: NorthlineColors.muted)),
                            ),
                            Expanded(child: Text(field.value, style: const TextStyle(fontSize: 13))),
                          ],
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          const _Section('Markers'),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [for (final marker in record.markers) _Marker(marker)],
          ),
          const SizedBox(height: 16),
          const _Section('Linked incidents'),
          for (final incident in record.incidents)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${incident.ref}   ${incident.date}',
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                  ),
                  Text(incident.title, style: const TextStyle(fontSize: 13)),
                ],
              ),
            ),
          if (linked.isNotEmpty) ...[
            const SizedBox(height: 8),
            const _Section('Linked records'),
            for (final item in linked)
              GestureDetector(
                onTap: () => onSelect(item.id),
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Text(
                    item.kind == PndKind.vehicle ? '${item.registration}  ${item.name}' : item.name,
                    style: const TextStyle(
                      fontSize: 13,
                      color: NorthlineColors.lake,
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ),
          ],
          const SizedBox(height: 12),
          PropButton(label: 'Save record', primary: true, onPressed: onSave),
        ],
      ),
    );
  }
}

class _Field {
  const _Field(this.label, this.value);
  final String label;
  final String value;
}

class _Section extends StatelessWidget {
  const _Section(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Text(
        label.toUpperCase(),
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.6,
          color: NorthlineColors.navy,
        ),
      ),
    );
  }
}

class _Marker extends StatelessWidget {
  const _Marker(this.label);
  final String label;

  @override
  Widget build(BuildContext context) {
    final colors = switch (label.toLowerCase()) {
      'stolen' => (const Color(0xFFF4D6D6), const Color(0xFF7A2E2E)),
      'warning' => (const Color(0xFFF6E6C8), const Color(0xFF6B4E16)),
      'missing' => (const Color(0xFFE4D8F2), const Color(0xFF4A3068)),
      'victim' => (const Color(0xFFD9E6F2), const Color(0xFF1E3A4C)),
      _ => (const Color(0xFFE7EEF2), const Color(0xFF1E3A4C)),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      color: colors.$1,
      child: Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: colors.$2)),
    );
  }
}

class _PhotoPlaceholder extends StatelessWidget {
  const _PhotoPlaceholder({required this.vehicle, required this.initials});

  final bool vehicle;
  final String initials;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 120,
      height: 148,
      decoration: BoxDecoration(
        color: const Color(0xFFE6EBEF),
        border: Border.all(color: const Color(0xFFB7C3CC)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CustomPaint(
            size: const Size(72, 64),
            painter: vehicle ? const _CarPainter() : const _PersonPainter(),
          ),
          if (!vehicle) ...[
            const SizedBox(height: 2),
            Text(initials, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: NorthlineColors.navy)),
          ],
          const SizedBox(height: 4),
          const Text(
            'NO PHOTOGRAPH',
            style: TextStyle(fontSize: 9, letterSpacing: 0.5, color: Color(0xFF5C6B76)),
          ),
        ],
      ),
    );
  }
}

class _PersonPainter extends CustomPainter {
  const _PersonPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = const Color(0xFF8AA0AE);
    canvas.drawCircle(Offset(size.width / 2, 16), 10, paint);
    final body = Path()
      ..moveTo(size.width / 2 - 22, 62)
      ..quadraticBezierTo(size.width / 2, 28, size.width / 2 + 22, 62)
      ..close();
    canvas.drawPath(body, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _CarPainter extends CustomPainter {
  const _CarPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF8AA0AE)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6
      ..strokeJoin = StrokeJoin.round;
    final body = Path()
      ..moveTo(6, 40)
      ..lineTo(14, 40)
      ..lineTo(22, 28)
      ..lineTo(46, 28)
      ..lineTo(54, 40)
      ..lineTo(66, 40);
    canvas.drawPath(body, paint);
    canvas.drawLine(const Offset(6, 40), const Offset(66, 40), paint);
    canvas.drawCircle(const Offset(22, 46), 5, paint);
    canvas.drawCircle(const Offset(50, 46), 5, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
