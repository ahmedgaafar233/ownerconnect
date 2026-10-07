import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl_phone_field/intl_phone_field.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/utils/phone_utils.dart';
import '../../../../core/widgets/app_loading_indicator.dart';
import '../../data/models/lease_inputs.dart';
import '../../data/models/profile_unit.dart';
import '../bloc/lease_bloc.dart';
import '../bloc/lease_event.dart';
import '../bloc/lease_state.dart';
import '../widgets/adult_form_sheet.dart';
import '../widgets/document_form_sheet.dart';
import '../widgets/id_photo.dart';
import '../widgets/unit_labels.dart';

final _e164 = RegExp(r'^\+\d{8,15}$');

/// A unit with no size class (no card allowance) takes this many adults — the
/// same default the server uses.
const _defaultMaxAdults = 10;

/// The owner renting one of their units out: the period, who the tenant is,
/// every other adult staying (each gets their own QR) and the papers going to
/// the village. The owner registers it themselves — the village is told, not asked.
class RentOutScreen extends StatefulWidget {
  const RentOutScreen({Key? key, required this.unit, this.pickPhoto = pickWithImagePicker}) : super(key: key);

  final ProfileUnit unit;
  final IdPhotoPicker pickPhoto;

  @override
  State<RentOutScreen> createState() => _RentOutScreenState();
}

class _RentOutScreenState extends State<RentOutScreen> {
  static const _short = 'SHORT';
  static const _long = 'LONG';

  final _nameController = TextEditingController();
  final _idController = TextEditingController();

  // Short stay by default: nothing moves financially unless the owner picks Long-term.
  String _term = _short;
  late DateTime _start;
  late DateTime _end;
  String _phone = '';
  int _occupants = 1;
  String? _photoPath;
  final _adults = <AdultInput>[];
  final _documents = <DocumentInput>[];

  @override
  void initState() {
    super.initState();
    _start = DateUtils.dateOnly(DateTime.now());
    _end = _start.add(const Duration(days: 30));
    _nameController.addListener(() => setState(() {}));
    _idController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _nameController.dispose();
    _idController.dispose();
    super.dispose();
  }

  int get _maxAdults => widget.unit.cardAllowance == null ? _defaultMaxAdults : widget.unit.cardAllowance!.clamp(1, 99);

  /// The tenant counts as one of the adults.
  bool get _canAddAdult => 1 + _adults.length < _maxAdults;

  bool get _canSubmit =>
      _nameController.text.trim().isNotEmpty &&
      _idController.text.trim().isNotEmpty &&
      _e164.hasMatch(_phone) &&
      _photoPath != null &&
      !_end.isBefore(_start);

  /// yyyy-MM-dd — the server reads these as the resort's own calendar days.
  String _ymd(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<void> _pickDate({required bool isStart}) async {
    final today = DateUtils.dateOnly(DateTime.now());
    final picked = await showDatePicker(
      context: context,
      initialDate: isStart ? _start : _end,
      // A rental can begin this month at the earliest: months already billed
      // to the owner can't be handed to a tenant afterwards (the server
      // enforces this too).
      firstDate: isStart ? DateTime(today.year, today.month, 1) : _start,
      lastDate: isStart ? today.add(const Duration(days: 365 * 2)) : _start.add(const Duration(days: 365 * 5)),
    );
    if (picked == null) return;
    setState(() {
      if (isStart) {
        _start = picked;
        if (_end.isBefore(picked)) _end = picked;
      } else {
        _end = picked;
      }
    });
  }

  Future<void> _choosePhoto() async {
    final path = await chooseAndPickPhoto(context, widget.pickPhoto);
    if (path != null && mounted) setState(() => _photoPath = path);
  }

  Future<void> _addAdult() async {
    final adult = await showAdultFormSheet(context, pickPhoto: widget.pickPhoto);
    if (adult != null && mounted) setState(() => _adults.add(adult));
  }

  Future<void> _addDocument() async {
    final document = await showDocumentFormSheet(context, pickPhoto: widget.pickPhoto);
    if (document != null && mounted) setState(() => _documents.add(document));
  }

  Future<void> _submit() async {
    if (!_canSubmit) return;
    final loc = AppLocalizations.of(context);
    final bloc = context.read<LeaseBloc>();

    // Long-term moves real money between accounts — say so before it happens.
    if (_term == _long) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text(loc.translate('rent_confirm_title')),
          content: Text(fillIn(loc.translate('rent_confirm_body'), [
            formatServerDate(dialogContext, _ymd(_start)),
            formatServerDate(dialogContext, _ymd(_end)),
          ])),
          actions: [
            TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: Text(loc.translate('cancel'))),
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: Text(loc.translate('rent_confirm_ok')),
            ),
          ],
        ),
      );
      if (confirmed != true) return;
    }

    bloc.add(LeaseSubmitted(
      unitId: widget.unit.id,
      term: _term,
      startDate: _ymd(_start),
      endDate: _ymd(_end),
      tenantName: _nameController.text.trim(),
      tenantPhone: _phone,
      tenantNationalId: _idController.text.trim(),
      idPhotoPath: _photoPath!,
      occupants: _occupants,
      adults: List.of(_adults),
      documents: List.of(_documents),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final dateLabel = MaterialLocalizations.of(context).formatMediumDate;

    return Scaffold(
      appBar: AppBar(title: Text('${loc.translate('rent_out_title')} · ${widget.unit.unitKey}')),
      body: BlocConsumer<LeaseBloc, LeaseState>(
        listener: (context, state) {
          if (state is LeaseCreatedState) {
            final message = state.failedUploads > 0
                ? fillIn(loc.translate('rent_uploads_failed'), ['${state.failedUploads}'])
                : loc.translate('rent_registered');
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
            Navigator.of(context).pop(true);
          } else if (state is LeaseErrorState) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.message), backgroundColor: AppColors.error),
            );
          }
        },
        builder: (context, state) {
          final isSending = state is LeaseWorkingState;

          return SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(loc.translate('rent_term_label'), style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  children: [
                    ChoiceChip(
                      label: Text(loc.translate('rent_term_short')),
                      selected: _term == _short,
                      onSelected: (_) => setState(() => _term = _short),
                    ),
                    ChoiceChip(
                      label: Text(loc.translate('rent_term_long')),
                      selected: _term == _long,
                      onSelected: (_) => setState(() => _term = _long),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  loc.translate(_term == _long ? 'rent_term_long_hint' : 'rent_term_short_hint'),
                  style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                ),
                const SizedBox(height: 20),
                Row(
                  children: [
                    Expanded(
                      child: _DateField(
                        label: loc.translate('rent_start_date'),
                        value: dateLabel(_start),
                        onTap: () => _pickDate(isStart: true),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _DateField(
                        label: loc.translate('rent_end_date'),
                        value: dateLabel(_end),
                        onTap: () => _pickDate(isStart: false),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Text(loc.translate('rent_tenant_section'), style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 12),
                TextField(
                  controller: _nameController,
                  textCapitalization: TextCapitalization.words,
                  decoration: InputDecoration(labelText: loc.translate('rent_tenant_name')),
                ),
                const SizedBox(height: 16),
                IntlPhoneField(
                  decoration: InputDecoration(
                    labelText: loc.translate('rent_tenant_phone'),
                    helperText: loc.translate('rent_tenant_phone_hint'),
                    helperMaxLines: 2,
                    counterText: '',
                  ),
                  initialCountryCode: 'EG',
                  // Only the number the tenant will sign in with matters; whether it's
                  // complete is judged from its length once normalised, never via
                  // isValidNumber() — that throws mid-typing.
                  onChanged: (phone) => setState(() => _phone = normalizedCompleteNumber(phone)),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _idController,
                  decoration: InputDecoration(labelText: loc.translate('rent_tenant_id')),
                ),
                const SizedBox(height: 16),
                IdPhotoTile(label: loc.translate('rent_id_photo'), path: _photoPath, onTap: _choosePhoto),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(child: Text(loc.translate('rent_occupants'))),
                    IconButton(
                      onPressed: _occupants > 1 ? () => setState(() => _occupants--) : null,
                      icon: const Icon(Icons.remove_circle_outline),
                    ),
                    Text('$_occupants', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                    IconButton(
                      onPressed: _occupants < 30 ? () => setState(() => _occupants++) : null,
                      icon: const Icon(Icons.add_circle_outline),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                _SectionHeader(
                  title: loc.translate('rent_adults_section'),
                  hint: loc.translate('rent_adults_hint'),
                  note: fillIn(loc.translate('rent_max_adults'), ['$_maxAdults']),
                ),
                for (var i = 0; i < _adults.length; i++)
                  _ChipRow(
                    icon: Icons.person_outline,
                    title: _adults[i].fullName,
                    subtitle: loc.translate(switch (_adults[i].relation) {
                      'SPOUSE' => 'adult_relation_spouse',
                      'FAMILY' => 'adult_relation_family',
                      _ => 'adult_relation_other',
                    }),
                    onRemove: () => setState(() => _adults.removeAt(i)),
                  ),
                OutlinedButton.icon(
                  onPressed: _canAddAdult ? _addAdult : null,
                  icon: const Icon(Icons.person_add_alt_1_outlined, size: 18),
                  label: Text(loc.translate('rent_add_adult')),
                ),
                const SizedBox(height: 20),
                _SectionHeader(title: loc.translate('rent_docs_section'), hint: loc.translate('rent_docs_hint')),
                for (var i = 0; i < _documents.length; i++)
                  _ChipRow(
                    icon: Icons.description_outlined,
                    title: loc.translate(documentKindLabelKey(_documents[i].kind)),
                    subtitle: _documents[i].label,
                    onRemove: () => setState(() => _documents.removeAt(i)),
                  ),
                OutlinedButton.icon(
                  onPressed: _addDocument,
                  icon: const Icon(Icons.note_add_outlined, size: 18),
                  label: Text(loc.translate('rent_add_document')),
                ),
                const SizedBox(height: 20),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.info_outline, size: 18, color: AppColors.textSecondary),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        loc.translate('rent_village_note'),
                        style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: isSending || !_canSubmit ? null : _submit,
                  child: isSending
                      ? const AppLoadingIndicator(size: 20, strokeWidth: 2)
                      : Text(loc.translate('rent_submit')),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.hint, this.note});

  final String title;
  final String hint;
  final String? note;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          Text(hint, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
          if (note != null) ...[
            const SizedBox(height: 2),
            Text(note!, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
          ],
        ],
      ),
    );
  }
}

/// A person or paper already added on the form, with a button to take it back out.
class _ChipRow extends StatelessWidget {
  const _ChipRow({required this.icon, required this.title, required this.subtitle, required this.onRemove});

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsetsDirectional.only(start: 12, end: 4, top: 4, bottom: 4),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Icon(icon, color: AppColors.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
                if (subtitle.isNotEmpty)
                  Text(subtitle, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
              ],
            ),
          ),
          IconButton(onPressed: onRemove, icon: const Icon(Icons.close, size: 20)),
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
