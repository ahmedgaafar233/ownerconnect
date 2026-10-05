import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/widgets/app_loading_indicator.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../bloc/visitor_pass_bloc.dart';
import '../bloc/visitor_pass_event.dart';
import '../bloc/visitor_pass_state.dart';

const _beachAccess = 'BEACH_ACCESS';

class _PassTypeOption {
  final String value;
  final String labelKey;
  final IconData icon;
  const _PassTypeOption(this.value, this.labelKey, this.icon);
}

const _passTypes = [
  _PassTypeOption(_beachAccess, 'pass_type_beach', Icons.beach_access),
  _PassTypeOption('VISITOR', 'pass_type_visitor', Icons.badge_outlined),
  _PassTypeOption('MAINTENANCE_WORKER', 'pass_type_worker', Icons.handyman_outlined),
];

/// A Tenant can only hold a beach/pool card — visitor and worker passes are
/// the Owner's to issue (enforced server-side too, see VisitorPassListCreateView).
List<_PassTypeOption> _passTypesFor(String role) =>
    role == 'TENANT' ? _passTypes.where((t) => t.value == _beachAccess).toList() : _passTypes;

class NewVisitorPassScreen extends StatefulWidget {
  const NewVisitorPassScreen({Key? key}) : super(key: key);

  @override
  State<NewVisitorPassScreen> createState() => _NewVisitorPassScreenState();
}

class _NewVisitorPassScreenState extends State<NewVisitorPassScreen> {
  final _nameController = TextEditingController();
  final _nationalIdController = TextEditingController();
  final _carPlateController = TextEditingController();

  List<Map<String, dynamic>> _units = [];
  Map<String, dynamic>? _unit;
  String _role = '';
  String _passType = _beachAccess;
  late DateTime _validFrom;
  late DateTime _validTo;
  bool _isLoadingUnits = true;
  bool _hasLoadError = false;

  @override
  void initState() {
    super.initState();
    final today = DateUtils.dateOnly(DateTime.now());
    _validFrom = today;
    _validTo = today.add(const Duration(days: 1));
    _nameController.addListener(() => setState(() {}));
    _loadUnits();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _nationalIdController.dispose();
    _carPlateController.dispose();
    super.dispose();
  }

  Future<void> _loadUnits() async {
    setState(() {
      _isLoadingUnits = true;
      _hasLoadError = false;
    });
    try {
      // Re-fetched on every open so "cards used" reflects passes issued since.
      final profile = await context.read<AuthBloc>().repository.fetchAndPersistProfile();
      final units = (profile['units'] as List? ?? const []).cast<Map<String, dynamic>>();
      if (mounted) {
        setState(() {
          _units = units;
          _unit = units.isNotEmpty ? units.first : null;
          _role = profile['role'] as String? ?? '';
          _isLoadingUnits = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _isLoadingUnits = false;
          _hasLoadError = true;
        });
      }
    }
  }

  int? get _allowance => _unit?['card_allowance'] as int?;
  int get _cardsUsed => _unit?['cards_used'] as int? ?? 0;

  /// Only beach/pool cards draw down the unit's allowance; a unit with no
  /// allowance set (null) is unrestricted.
  bool get _cardsFull => _passType == _beachAccess && _allowance != null && _cardsUsed >= _allowance!;

  bool get _canSubmit => _unit != null && _nameController.text.trim().isNotEmpty && !_cardsFull;

  /// A visitor comes for a day — staying overnight is a rental, which this
  /// pass doesn't cover — so a guest pass takes one date; cards take a range.
  bool get _isDayVisit => _passType == 'VISITOR';

  Future<void> _pickDate({required bool isFrom}) async {
    final today = DateUtils.dateOnly(DateTime.now());
    final picked = await showDatePicker(
      context: context,
      initialDate: isFrom ? _validFrom : _validTo,
      firstDate: isFrom ? today : _validFrom,
      lastDate: today.add(const Duration(days: 365)),
    );
    if (picked == null) return;
    setState(() {
      if (isFrom) {
        _validFrom = picked;
        if (_validTo.isBefore(picked) || _isDayVisit) _validTo = picked;
      } else {
        _validTo = picked;
      }
    });
  }

  /// yyyy-MM-dd — the server reads these as the resort's own calendar days.
  String _ymd(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  void _submit(BuildContext context) {
    if (!_canSubmit) return;
    context.read<VisitorPassBloc>().add(
          CreateVisitorPassEvent(
            unitId: _unit!['id'] as int,
            passType: _passType,
            visitorName: _nameController.text.trim(),
            nationalId: _nationalIdController.text.trim(),
            carPlate: _carPlateController.text.trim(),
            startDate: _ymd(_validFrom),
            endDate: _ymd(_isDayVisit ? _validFrom : _validTo),
          ),
        );
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('create_pass'))),
      body: BlocConsumer<VisitorPassBloc, VisitorPassState>(
        listener: (context, state) {
          if (state is VisitorPassCreatedState) {
            // In a resort where Security confirms each pass, it's a request
            // that isn't usable yet — say so rather than "created".
            final waiting = state.pass.status == 'PENDING';
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(loc.translate(waiting ? 'pass_request_sent' : 'pass_created'))),
            );
            Navigator.of(context).pop();
          } else if (state is VisitorPassErrorState) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.message), backgroundColor: AppColors.error),
            );
          }
        },
        builder: (context, state) {
          final isSending = state is VisitorPassLoadingState;

          if (_isLoadingUnits) {
            return const Center(child: AppLoadingIndicator());
          }
          if (_hasLoadError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      loc.translate('load_unit_error'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton(
                      onPressed: _loadUnits,
                      child: Text(loc.translate('retry_button')),
                    ),
                  ],
                ),
              ),
            );
          }
          if (_unit == null) {
            return Center(child: Text(loc.translate('contact_us_no_unit')));
          }

          final passTypes = _passTypesFor(_role);
          final dateLabel = MaterialLocalizations.of(context).formatMediumDate;

          return SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_units.length > 1) ...[
                  DropdownButtonFormField<int>(
                    initialValue: _unit!['id'] as int,
                    decoration: InputDecoration(labelText: loc.translate('unit')),
                    items: _units
                        .map((u) => DropdownMenuItem<int>(
                              value: u['id'] as int,
                              child: Text(u['unit_key'] as String? ?? ''),
                            ))
                        .toList(),
                    onChanged: (id) => setState(() {
                      _unit = _units.firstWhere((u) => u['id'] == id);
                    }),
                  ),
                  const SizedBox(height: 20),
                ],
                if (passTypes.length > 1) ...[
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: passTypes.map((type) {
                      return ChoiceChip(
                        avatar: Icon(type.icon, size: 18),
                        label: Text(loc.translate(type.labelKey)),
                        selected: _passType == type.value,
                        onSelected: (_) => setState(() {
                          _passType = type.value;
                          if (_isDayVisit) _validTo = _validFrom;
                        }),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 20),
                ],
                if (_passType == _beachAccess && _allowance != null) ...[
                  _CardAllowanceBanner(
                    used: _cardsUsed,
                    allowance: _allowance!,
                    isFull: _cardsFull,
                    usedLabel: loc.translate('cards_used'),
                    fullHint: loc.translate('cards_full_hint'),
                  ),
                  const SizedBox(height: 20),
                ],
                TextField(
                  controller: _nameController,
                  textCapitalization: TextCapitalization.words,
                  decoration: InputDecoration(labelText: loc.translate('pass_holder_name')),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _nationalIdController,
                  decoration: InputDecoration(labelText: loc.translate('pass_national_id')),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _carPlateController,
                  textCapitalization: TextCapitalization.characters,
                  decoration: InputDecoration(labelText: loc.translate('pass_car_plate')),
                ),
                const SizedBox(height: 16),
                if (_isDayVisit) ...[
                  _DateField(
                    label: loc.translate('pass_visit_date'),
                    value: dateLabel(_validFrom),
                    onTap: () => _pickDate(isFrom: true),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    loc.translate('pass_day_visit_hint'),
                    style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                  ),
                ] else
                  Row(
                    children: [
                      Expanded(
                        child: _DateField(
                          label: loc.translate('pass_valid_from'),
                          value: dateLabel(_validFrom),
                          onTap: () => _pickDate(isFrom: true),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _DateField(
                          label: loc.translate('pass_valid_to'),
                          value: dateLabel(_validTo),
                          onTap: () => _pickDate(isFrom: false),
                        ),
                      ),
                    ],
                  ),
                const SizedBox(height: 28),
                ElevatedButton(
                  onPressed: isSending || !_canSubmit ? null : () => _submit(context),
                  child: isSending
                      ? const AppLoadingIndicator(size: 20, strokeWidth: 2)
                      : Text(loc.translate('submit_pass')),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _CardAllowanceBanner extends StatelessWidget {
  const _CardAllowanceBanner({
    required this.used,
    required this.allowance,
    required this.isFull,
    required this.usedLabel,
    required this.fullHint,
  });

  final int used;
  final int allowance;
  final bool isFull;
  final String usedLabel;
  final String fullHint;

  @override
  Widget build(BuildContext context) {
    final color = isFull ? AppColors.error : AppColors.primary;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isFull ? AppColors.error.withValues(alpha: 0.08) : AppColors.glassFill,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color),
      ),
      child: Row(
        children: [
          Icon(Icons.credit_card, color: color),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$usedLabel: $used / $allowance',
                  style: TextStyle(fontWeight: FontWeight.w700, color: color),
                ),
                if (isFull) ...[
                  const SizedBox(height: 4),
                  Text(fullHint, style: const TextStyle(color: AppColors.textSecondary)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DateField extends StatelessWidget {
  const _DateField({required this.label, required this.value, required this.onTap});

  final String label;
  final String value;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: InputDecorator(
        decoration: InputDecoration(labelText: label, suffixIcon: const Icon(Icons.calendar_today, size: 18)),
        child: Text(value),
      ),
    );
  }
}
