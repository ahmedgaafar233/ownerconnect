import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/widgets/app_loading_indicator.dart';
import '../../../support/presentation/widgets/pass_qr_dialog.dart';
import '../../data/models/lease_model.dart';
import '../../data/models/profile_unit.dart';
import '../bloc/lease_bloc.dart';
import '../bloc/lease_event.dart';
import '../bloc/lease_state.dart';
import '../widgets/adult_form_sheet.dart';
import '../widgets/document_form_sheet.dart';
import '../widgets/id_photo.dart';
import '../widgets/lease_status_badge.dart';
import '../widgets/meter_readings_card.dart';
import '../widgets/unit_labels.dart';

/// One rental of the owner's: who the tenant is, everyone staying and their
/// QR codes, the papers sent to the village, and what the tenant still owes —
/// plus extending, renewing or ending it.
class LeaseDetailsScreen extends StatefulWidget {
  const LeaseDetailsScreen({
    Key? key,
    required this.unit,
    required this.lease,
    this.pickPhoto = pickWithImagePicker,
  }) : super(key: key);

  final ProfileUnit unit;
  final LeaseModel lease;
  final IdPhotoPicker pickPhoto;

  @override
  State<LeaseDetailsScreen> createState() => _LeaseDetailsScreenState();
}

class _LeaseDetailsScreenState extends State<LeaseDetailsScreen> {
  late LeaseModel _lease = widget.lease;

  /// Set once anything changed, so the profile behind refreshes when this closes.
  bool _changed = false;

  String _ymd(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<bool> _confirm(String title, String body, String action, {bool danger = false}) async {
    final loc = AppLocalizations.of(context);
    final result = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: Text(loc.translate('cancel'))),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            style: danger ? TextButton.styleFrom(foregroundColor: AppColors.error) : null,
            child: Text(action),
          ),
        ],
      ),
    );
    return result == true;
  }

  Future<void> _end() async {
    final loc = AppLocalizations.of(context);
    final bloc = context.read<LeaseBloc>();
    final ok = await _confirm(
      loc.translate('lease_end_confirm_title'),
      loc.translate('lease_end_confirm_body'),
      loc.translate('lease_end_button'),
      danger: true,
    );
    if (ok && _lease.id != null) bloc.add(LeaseEndRequested(_lease.id!));
  }

  Future<void> _extend() async {
    final bloc = context.read<LeaseBloc>();
    final end = DateTime.tryParse(_lease.endDate);
    final start = DateTime.tryParse(_lease.startDate);
    if (end == null || start == null || _lease.id == null) return;
    final picked = await showDatePicker(
      context: context,
      helpText: AppLocalizations.of(context).translate('lease_extend_title'),
      initialDate: end.add(const Duration(days: 30)),
      firstDate: end.add(const Duration(days: 1)),
      lastDate: start.add(const Duration(days: 365 * 10)),
    );
    if (picked != null) bloc.add(LeaseExtended(_lease.id!, _ymd(picked)));
  }

  Future<void> _renew() async {
    final bloc = context.read<LeaseBloc>();
    final result = await showDialog<_Renewal>(
      context: context,
      builder: (_) => _RenewDialog(lease: _lease),
    );
    if (result != null && _lease.id != null) {
      bloc.add(LeaseRenewed(_lease.id!, startDate: _ymd(result.start), endDate: _ymd(result.end), term: result.term));
    }
  }

  Future<void> _addAdult() async {
    final bloc = context.read<LeaseBloc>();
    final adult = await showAdultFormSheet(context, pickPhoto: widget.pickPhoto);
    if (adult != null && _lease.id != null) bloc.add(LeaseAdultAdded(_lease.id!, adult));
  }

  Future<void> _addDocument() async {
    final bloc = context.read<LeaseBloc>();
    final document = await showDocumentFormSheet(context, pickPhoto: widget.pickPhoto);
    if (document != null && _lease.id != null) bloc.add(LeaseDocumentAdded(_lease.id!, document));
  }

  Future<void> _removeAdult(LeaseAdultModel adult) async {
    final loc = AppLocalizations.of(context);
    final bloc = context.read<LeaseBloc>();
    final ok = await _confirm(
      loc.translate('lease_remove'),
      fillIn(loc.translate('lease_remove_adult_confirm'), [adult.fullName]),
      loc.translate('lease_remove'),
      danger: true,
    );
    if (ok && _lease.id != null) bloc.add(LeaseAdultRemoved(_lease.id!, adult.id));
  }

  Future<void> _removeDocument(LeaseDocumentModel document) async {
    final loc = AppLocalizations.of(context);
    final bloc = context.read<LeaseBloc>();
    final ok = await _confirm(
      loc.translate('lease_remove'),
      loc.translate('lease_remove_doc_confirm'),
      loc.translate('lease_remove'),
      danger: true,
    );
    if (ok && _lease.id != null) bloc.add(LeaseDocumentRemoved(_lease.id!, document.id));
  }

  void _showQr(LeasePass pass, String name) {
    showDialog<void>(
      context: context,
      builder: (_) => PassQrDialog(
        pass: pass.toVisitorPass(unitId: widget.unit.id, unitKey: widget.unit.unitKey, name: name),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final lease = _lease;

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) Navigator.of(context).pop(_changed);
      },
      child: Scaffold(
        appBar: AppBar(title: Text('${loc.translate('lease_details_title')} · ${widget.unit.unitKey}')),
        body: BlocConsumer<LeaseBloc, LeaseState>(
          listener: (context, state) {
            final messenger = ScaffoldMessenger.of(context);
            if (state is LeaseEndedState) {
              messenger.showSnackBar(SnackBar(content: Text(loc.translate('lease_ended_done'))));
              Navigator.of(context).pop(true);
            } else if (state is LeaseRenewedState) {
              messenger.showSnackBar(SnackBar(content: Text(loc.translate('lease_renewed_done'))));
              Navigator.of(context).pop(true);
            } else if (state is LeaseChangedState) {
              final extended = state.lease.endDate != _lease.endDate;
              setState(() {
                _lease = state.lease;
                _changed = true;
              });
              if (extended) messenger.showSnackBar(SnackBar(content: Text(loc.translate('lease_extended_done'))));
            } else if (state is LeaseErrorState) {
              messenger.showSnackBar(SnackBar(content: Text(state.message), backgroundColor: AppColors.error));
            }
          },
          builder: (context, state) {
            final isWorking = state is LeaseWorkingState;
            final balance = lease.tenantBalance;

            return ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        lease.tenantName,
                        style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
                      ),
                    ),
                    LeaseStatusBadge(status: lease.status),
                  ],
                ),
                const SizedBox(height: 16),
                _Row(label: loc.translate('lease_tenant_phone'), value: lease.tenantPhone),
                _Row(label: loc.translate('lease_tenant_id'), value: lease.tenantNationalId),
                _Row(label: loc.translate('lease_occupants'), value: '${lease.occupants}'),
                _Row(
                  label: loc.translate('lease_period'),
                  value: '${formatServerDate(context, lease.startDate)} – ${formatServerDate(context, lease.endDate)}',
                ),
                _Row(
                  label: loc.translate('lease_term'),
                  value: loc.translate(lease.isLong ? 'rent_term_long' : 'rent_term_short'),
                ),
                if (lease.isLong && balance != null) ...[
                  const SizedBox(height: 16),
                  // "Cleared" only means something once the rental is over: while
                  // it runs, a zero balance just means nothing has been billed yet.
                  if (lease.tenantCleared == true && lease.isEnded)
                    _Banner(
                      color: AppColors.success,
                      icon: Icons.verified_outlined,
                      text: loc.translate('lease_tenant_cleared'),
                    )
                  else
                    _Banner(
                      color: lease.tenantCleared == true ? AppColors.primary : AppColors.warning,
                      icon: lease.tenantCleared == true ? Icons.check_circle_outline : Icons.hourglass_bottom,
                      text: '${loc.translate('lease_tenant_balance')}: $balance EGP',
                    ),
                ],
                const SizedBox(height: 24),
                _SectionTitle(loc.translate('meter_section')),
                MeterReadingsCard(readings: lease.meterReadings),
                const SizedBox(height: 24),
                _SectionTitle(loc.translate('lease_qr_section')),
                if (!lease.isLong) ...[
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      loc.translate('lease_qr_short_hint'),
                      style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                    ),
                  ),
                ],
                if (lease.access != null)
                  _PersonRow(
                    icon: Icons.person,
                    name: lease.tenantName,
                    detail: loc.translate('lease_qr_tenant'),
                    validUntil: fillIn(loc.translate('lease_valid_until'), [formatServerDate(context, lease.endDate)]),
                    pass: lease.access,
                    showLabel: loc.translate('lease_qr_show'),
                    onShow: () => _showQr(lease.access!, lease.tenantName),
                  ),
                for (final adult in lease.adults)
                  _PersonRow(
                    icon: Icons.person_outline,
                    name: adult.fullName,
                    detail: loc.translate(switch (adult.relation) {
                      'SPOUSE' => 'adult_relation_spouse',
                      'FAMILY' => 'adult_relation_family',
                      _ => 'adult_relation_other',
                    }),
                    validUntil: fillIn(loc.translate('lease_valid_until'), [formatServerDate(context, lease.endDate)]),
                    pass: adult.access,
                    showLabel: loc.translate('lease_qr_show'),
                    onShow: adult.access == null ? null : () => _showQr(adult.access!, adult.fullName),
                    onRemove: lease.canEnd && !isWorking ? () => _removeAdult(adult) : null,
                  ),
                if (lease.canEnd)
                  OutlinedButton.icon(
                    onPressed: lease.canAddAdult && !isWorking ? _addAdult : null,
                    icon: const Icon(Icons.person_add_alt_1_outlined, size: 18),
                    label: Text(loc.translate('lease_add_adult')),
                  ),
                if (lease.canEnd)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      fillIn(loc.translate('rent_max_adults'), ['${lease.maxAdults}']),
                      style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                    ),
                  ),
                const SizedBox(height: 24),
                _SectionTitle(loc.translate('lease_docs_section')),
                for (final document in lease.documents)
                  _PersonRow(
                    icon: Icons.description_outlined,
                    name: loc.translate(documentKindLabelKey(document.kind)),
                    detail: document.label,
                    onRemove: !isWorking ? () => _removeDocument(document) : null,
                  ),
                OutlinedButton.icon(
                  onPressed: isWorking ? null : _addDocument,
                  icon: const Icon(Icons.note_add_outlined, size: 18),
                  label: Text(loc.translate('rent_add_document')),
                ),
                const SizedBox(height: 28),
                if (lease.canEnd)
                  OutlinedButton.icon(
                    onPressed: isWorking ? null : _extend,
                    icon: const Icon(Icons.event_repeat_outlined, size: 18),
                    label: Text(loc.translate('lease_extend_button')),
                  ),
                if (lease.id != null && lease.status != 'CANCELLED') ...[
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: isWorking ? null : _renew,
                    icon: const Icon(Icons.autorenew, size: 18),
                    label: Text(loc.translate('lease_renew_button')),
                  ),
                ],
                if (lease.canEnd) ...[
                  const SizedBox(height: 24),
                  OutlinedButton(
                    onPressed: isWorking ? null : _end,
                    style: OutlinedButton.styleFrom(foregroundColor: AppColors.error),
                    child: isWorking
                        ? const AppLoadingIndicator(size: 20, strokeWidth: 2)
                        : Text(loc.translate('lease_end_button')),
                  ),
                ],
              ],
            );
          },
        ),
      ),
    );
  }
}

/// What the owner picks in the renew dialog.
class _Renewal {
  const _Renewal(this.start, this.end, this.term);

  final DateTime start;
  final DateTime end;
  final String term;
}

class _RenewDialog extends StatefulWidget {
  const _RenewDialog({required this.lease});

  final LeaseModel lease;

  @override
  State<_RenewDialog> createState() => _RenewDialogState();
}

class _RenewDialogState extends State<_RenewDialog> {
  late DateTime _start;
  late DateTime _end;
  late String _term = widget.lease.term.isEmpty ? 'SHORT' : widget.lease.term;

  @override
  void initState() {
    super.initState();
    final today = DateUtils.dateOnly(DateTime.now());
    final current = DateTime.tryParse(widget.lease.endDate);
    // Straight on from the current period if it's still running, else from today.
    _start = current != null && !current.isBefore(today) ? current.add(const Duration(days: 1)) : today;
    _end = _start.add(const Duration(days: 30));
  }

  Future<void> _pick({required bool isStart}) async {
    final today = DateUtils.dateOnly(DateTime.now());
    final picked = await showDatePicker(
      context: context,
      initialDate: isStart ? _start : _end,
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

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final format = MaterialLocalizations.of(context).formatMediumDate;

    return AlertDialog(
      title: Text(loc.translate('lease_renew_title')),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(loc.translate('lease_renew_hint'), style: const TextStyle(color: AppColors.textSecondary)),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            children: [
              ChoiceChip(
                label: Text(loc.translate('rent_term_short')),
                selected: _term == 'SHORT',
                onSelected: (_) => setState(() => _term = 'SHORT'),
              ),
              ChoiceChip(
                label: Text(loc.translate('rent_term_long')),
                selected: _term == 'LONG',
                onSelected: (_) => setState(() => _term = 'LONG'),
              ),
            ],
          ),
          const SizedBox(height: 12),
          InkWell(
            onTap: () => _pick(isStart: true),
            child: InputDecorator(
              decoration: InputDecoration(
                labelText: loc.translate('rent_start_date'),
                suffixIcon: const Icon(Icons.calendar_today, size: 18),
              ),
              child: Text(format(_start)),
            ),
          ),
          const SizedBox(height: 12),
          InkWell(
            onTap: () => _pick(isStart: false),
            child: InputDecorator(
              decoration: InputDecoration(
                labelText: loc.translate('rent_end_date'),
                suffixIcon: const Icon(Icons.calendar_today, size: 18),
              ),
              child: Text(format(_end)),
            ),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: Text(loc.translate('cancel'))),
        TextButton(
          onPressed: () => Navigator.of(context).pop(_Renewal(_start, _end, _term)),
          child: Text(loc.translate('lease_renew_button')),
        ),
      ],
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(text, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
    );
  }
}

/// A person (with their QR) or a paper in the rental, with optional remove.
class _PersonRow extends StatelessWidget {
  const _PersonRow({
    required this.icon,
    required this.name,
    required this.detail,
    this.validUntil,
    this.pass,
    this.showLabel,
    this.onShow,
    this.onRemove,
  });

  final IconData icon;
  final String name;
  final String detail;
  final String? validUntil;
  final LeasePass? pass;
  final String? showLabel;
  final VoidCallback? onShow;
  final VoidCallback? onRemove;

  @override
  Widget build(BuildContext context) {
    final working = pass?.isActive ?? true;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsetsDirectional.only(start: 12, end: 4, top: 6, bottom: 6),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Icon(icon, color: working ? AppColors.primary : AppColors.textTertiary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name, style: const TextStyle(fontWeight: FontWeight.w600)),
                if (detail.isNotEmpty)
                  Text(detail, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                if (validUntil != null)
                  Text(validUntil!, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
              ],
            ),
          ),
          if (onShow != null && (pass?.isActive ?? false))
            TextButton.icon(
              onPressed: onShow,
              icon: const Icon(Icons.qr_code_2, size: 20),
              label: Text(showLabel ?? ''),
            ),
          if (onRemove != null) IconButton(onPressed: onRemove, icon: const Icon(Icons.close, size: 20)),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Text(label, style: const TextStyle(color: AppColors.textSecondary)),
          const SizedBox(width: 12),
          Expanded(
            child: Text(value, textAlign: TextAlign.end, style: const TextStyle(fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.color, required this.icon, required this.text});

  final Color color;
  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color),
      ),
      child: Row(
        children: [
          Icon(icon, color: color),
          const SizedBox(width: 12),
          Expanded(child: Text(text, style: TextStyle(color: color, fontWeight: FontWeight.w700))),
        ],
      ),
    );
  }
}
