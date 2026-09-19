import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../support/presentation/bloc/support_bloc.dart';
import '../../../support/presentation/bloc/support_event.dart';
import '../../../support/presentation/bloc/support_state.dart';
import '../../data/models/charge_model.dart';
import '../bloc/financial_bloc.dart';
import '../bloc/financial_event.dart';
import '../bloc/financial_state.dart';
import '../widgets/highlighted_date_picker.dart';
import 'payment_checkout_screen.dart';

/// Shown before any actual payment happens — the "Pay Now" button used to
/// jump straight into an online checkout, but online is only one of the
/// resort's real payment paths. Defer/Payment-Plan only make sense for a
/// single charge at a time (the backend's PaymentDeferral/PaymentPlan each
/// point at exactly one Charge), so those two options only show when
/// exactly one charge is selected; paying online or at the office both
/// already support a multi-charge selection.
class PaymentOptionsScreen extends StatefulWidget {
  final List<ChargeModel> selectedCharges;

  const PaymentOptionsScreen({Key? key, required this.selectedCharges}) : super(key: key);

  @override
  State<PaymentOptionsScreen> createState() => _PaymentOptionsScreenState();
}

class _PaymentOptionsScreenState extends State<PaymentOptionsScreen> {
  bool _isPartial = false;
  final _partialAmountController = TextEditingController();
  DateTime? _remainingDate;

  // _payAtOffice now dispatches one CreateTicketEvent per distinct unit —
  // the BlocListener below reacts to every TicketCreatedState it sees, so
  // without this counter it would pop the screen once per ticket and crash
  // go_router on the second pop (confirmed on-device). Only pop once every
  // dispatched ticket has actually been created.
  int _pendingOfficeTickets = 0;

  double get _total => widget.selectedCharges.fold(0, (sum, c) => sum + c.remainingBalance);

  bool get _singleCharge => widget.selectedCharges.length == 1;

  Map<String, double> get _byUnit {
    final map = <String, double>{};
    for (final c in widget.selectedCharges) {
      map[c.unitKey] = (map[c.unitKey] ?? 0) + c.remainingBalance;
    }
    return map;
  }

  @override
  void dispose() {
    _partialAmountController.dispose();
    super.dispose();
  }

  Future<void> _pickDeferDate(BuildContext context) async {
    final today = DateTime.now();
    final charge = widget.selectedCharges.first;
    final picked = await showHighlightedDatePicker(
      context: context,
      initialDate: today.add(const Duration(days: 1)),
      firstDate: today.add(const Duration(days: 1)),
      lastDate: today.add(const Duration(days: 3)),
      chargeIssuedDate: DateTime.tryParse(charge.createdAt),
    );
    if (picked == null || !context.mounted) return;

    final dateStr =
        '${picked.year.toString().padLeft(4, '0')}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
    context.read<FinancialBloc>().add(
          DeferChargeEvent(chargeId: widget.selectedCharges.first.id, deferredTo: dateStr),
        );
  }

  Future<void> _requestPaymentPlan(BuildContext context) async {
    final charge = widget.selectedCharges.first;
    final installments = await showDialog<List<Map<String, String>>>(
      context: context,
      builder: (_) => _PaymentPlanDialog(totalAmount: _total, chargeIssuedDate: DateTime.tryParse(charge.createdAt)),
    );
    if (installments == null || installments.isEmpty || !context.mounted) return;

    context.read<FinancialBloc>().add(
          CreatePaymentPlanEvent(chargeId: widget.selectedCharges.first.id, installments: installments),
        );
  }

  void _payAtOffice(BuildContext context) async {
    final loc = AppLocalizations.of(context);
    final today = DateTime.now();
    final charge = widget.selectedCharges.first;
    final picked = await showHighlightedDatePicker(
      context: context,
      initialDate: today.add(const Duration(days: 1)),
      firstDate: today,
      lastDate: today.add(const Duration(days: 60)),
      chargeIssuedDate: DateTime.tryParse(charge.createdAt),
    );
    if (picked == null || !context.mounted) return;

    final dateStr = '${picked.year}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';

    // One ticket per distinct unit involved — the accounts office needs a
    // separate visit line per unit even when it's one combined visit, and
    // SupportBloc is provided app-wide so these keep processing even after
    // this screen pops once every dispatched ticket has been created.
    final byUnitId = <int, List<ChargeModel>>{};
    for (final c in widget.selectedCharges) {
      byUnitId.putIfAbsent(c.unit, () => []).add(c);
    }
    _pendingOfficeTickets = byUnitId.length;
    for (final entry in byUnitId.entries) {
      final unitTotal = entry.value.fold<double>(0, (sum, c) => sum + c.remainingBalance);
      context.read<SupportBloc>().add(
            CreateTicketEvent(
              unitId: entry.key,
              category: 'ACCOUNTS',
              priority: 'MEDIUM',
              subject: loc.translate('pay_at_office_subject'),
              description:
                  '${loc.translate('pay_at_office_description')} $dateStr — ${loc.translate('amount')}: ${unitTotal.toStringAsFixed(2)} EGP.',
            ),
          );
    }
  }

  Future<void> _pickRemainingDueDate(BuildContext context) async {
    final today = DateTime.now();
    final picked = await showHighlightedDatePicker(
      context: context,
      initialDate: today.add(const Duration(days: 1)),
      firstDate: today.add(const Duration(days: 1)),
      lastDate: today.add(const Duration(days: 5)),
    );
    if (picked == null) return;
    setState(() => _remainingDate = picked);
  }

  void _payOnline(BuildContext context) {
    final loc = AppLocalizations.of(context);
    if (!_isPartial) {
      context.read<FinancialBloc>().add(
            InitiatePaymentEvent(chargeIds: widget.selectedCharges.map((c) => c.id).toList()),
          );
      return;
    }

    final amount = double.tryParse(_partialAmountController.text.trim());
    if (amount == null || amount <= 0 || amount > _total) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(loc.translate('pay_partial_invalid_amount')), backgroundColor: AppColors.error),
      );
      return;
    }
    String? remainingDueDate;
    if (amount < _total) {
      if (_remainingDate == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(loc.translate('pay_partial_date_required')), backgroundColor: AppColors.error),
        );
        return;
      }
      remainingDueDate =
          '${_remainingDate!.year.toString().padLeft(4, '0')}-${_remainingDate!.month.toString().padLeft(2, '0')}-${_remainingDate!.day.toString().padLeft(2, '0')}';
    }

    context.read<FinancialBloc>().add(
          InitiatePaymentEvent(
            chargeIds: widget.selectedCharges.map((c) => c.id).toList(),
            payAmount: amount,
            remainingDueDate: remainingDueDate,
          ),
        );
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('payment_options_title'))),
      body: MultiBlocListener(
        listeners: [
          BlocListener<FinancialBloc, FinancialState>(
            listener: (context, state) {
              if (state is ChargeDeferredState) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('${loc.translate('deferred_to_label')} ${state.deferredTo}')),
                );
                Navigator.of(context).pop();
              } else if (state is PaymentPlanCreatedState) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(loc.translate('payment_plan_pending'))),
                );
                Navigator.of(context).pop();
              } else if (state is FinancialErrorState) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(state.errorMessage), backgroundColor: AppColors.error),
                );
              } else if (state is PaymentInitiatedState) {
                final checkoutUrl = state.paymentSession['checkout_url'] as String;
                final merchantOrderId = state.paymentSession['merchant_order_id'] as String;
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => BlocProvider.value(
                      value: context.read<FinancialBloc>(),
                      child: PaymentCheckoutScreen(checkoutUrl: checkoutUrl, merchantOrderId: merchantOrderId),
                    ),
                  ),
                );
              }
            },
          ),
          BlocListener<SupportBloc, SupportState>(
            listener: (context, state) {
              if (state is TicketCreatedState) {
                if (_pendingOfficeTickets > 0) {
                  _pendingOfficeTickets -= 1;
                }
                if (_pendingOfficeTickets == 0) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(loc.translate('pay_at_office_confirmed'))),
                  );
                  Navigator.of(context).pop();
                }
              } else if (state is SupportErrorState) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(state.message), backgroundColor: AppColors.error),
                );
              }
            },
          ),
        ],
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                '${loc.translate('amount')}: ${_total.toStringAsFixed(2)} EGP',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
              ),
              if (_byUnit.length > 1) ...[
                const SizedBox(height: 8),
                Text(
                  loc.translate('per_unit_selection_note'),
                  style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                ),
                const SizedBox(height: 8),
                ..._byUnit.entries.map(
                  (e) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(e.key, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                        Text('${e.value.toStringAsFixed(2)} EGP', style: const TextStyle(fontSize: 13)),
                      ],
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 16),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                value: _isPartial,
                onChanged: (v) => setState(() => _isPartial = v),
                title: Text(loc.translate('pay_partial_toggle'), style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              ),
              if (_isPartial) ...[
                TextField(
                  controller: _partialAmountController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: InputDecoration(labelText: loc.translate('pay_partial_amount_label')),
                  onChanged: (_) => setState(() {}),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: () => _pickRemainingDueDate(context),
                  icon: const Icon(Icons.calendar_month_outlined),
                  label: Text(
                    _remainingDate != null
                        ? '${loc.translate('remaining_due_date_label')}: ${_remainingDate!.year}-${_remainingDate!.month.toString().padLeft(2, '0')}-${_remainingDate!.day.toString().padLeft(2, '0')}'
                        : loc.translate('remaining_due_date_label'),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  loc.translate('pay_partial_cap_note'),
                  style: const TextStyle(fontSize: 11, color: AppColors.textSecondary),
                ),
              ],
              const SizedBox(height: 24),
              _OptionTile(
                icon: Icons.language,
                title: loc.translate('pay_online_option'),
                subtitle: loc.translate('pay_online_subtitle'),
                onTap: () => _payOnline(context),
              ),
              if (_singleCharge) ...[
                _OptionTile(
                  icon: Icons.event_available,
                  title: loc.translate('defer_option'),
                  subtitle: loc.translate('defer_subtitle'),
                  onTap: () => _pickDeferDate(context),
                ),
                _OptionTile(
                  icon: Icons.calendar_month,
                  title: loc.translate('payment_plan_option'),
                  subtitle: loc.translate('payment_plan_subtitle'),
                  onTap: () => _requestPaymentPlan(context),
                ),
              ] else
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Text(
                    loc.translate('defer_multi_charge_note'),
                    style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                  ),
                ),
              _OptionTile(
                icon: Icons.storefront,
                title: loc.translate('pay_at_office_option'),
                subtitle: loc.translate('pay_at_office_subtitle'),
                onTap: () => _payAtOffice(context),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _OptionTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _OptionTile({required this.icon, required this.title, required this.subtitle, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: Icon(icon, color: AppColors.primary),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(subtitle, style: const TextStyle(fontSize: 12)),
        onTap: onTap,
      ),
    );
  }
}

/// Lets the owner propose installments (date + amount rows) for a payment
/// plan request. Kept intentionally simple for v1 — approve/reject the
/// proposal as a whole, no counter-proposal editing.
class _PaymentPlanDialog extends StatefulWidget {
  final double totalAmount;
  final DateTime? chargeIssuedDate;

  const _PaymentPlanDialog({required this.totalAmount, this.chargeIssuedDate});

  @override
  State<_PaymentPlanDialog> createState() => _PaymentPlanDialogState();
}

class _PaymentPlanDialogState extends State<_PaymentPlanDialog> {
  final List<_InstallmentRow> _rows = [_InstallmentRow()];

  @override
  void dispose() {
    for (final row in _rows) {
      row.amountController.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return AlertDialog(
      title: Text(loc.translate('payment_plan_option')),
      content: SizedBox(
        width: double.maxFinite,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final row in _rows)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () async {
                            final today = DateTime.now();
                            final picked = await showHighlightedDatePicker(
                              context: context,
                              initialDate: today.add(const Duration(days: 7)),
                              firstDate: today.add(const Duration(days: 1)),
                              lastDate: today.add(const Duration(days: 365)),
                              chargeIssuedDate: widget.chargeIssuedDate,
                            );
                            if (picked != null) {
                              setState(() => row.date = picked);
                            }
                          },
                          child: Text(
                            row.date == null
                                ? loc.translate('pick_date')
                                : '${row.date!.year}-${row.date!.month.toString().padLeft(2, '0')}-${row.date!.day.toString().padLeft(2, '0')}',
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          controller: row.amountController,
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                          decoration: InputDecoration(labelText: loc.translate('amount')),
                        ),
                      ),
                    ],
                  ),
                ),
              TextButton.icon(
                onPressed: () => setState(() => _rows.add(_InstallmentRow())),
                icon: const Icon(Icons.add),
                label: Text(loc.translate('add_installment')),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(loc.translate('cancel')),
        ),
        ElevatedButton(
          onPressed: () {
            final installments = <Map<String, String>>[];
            for (final row in _rows) {
              final amountText = row.amountController.text.trim();
              if (row.date == null || amountText.isEmpty) continue;
              final dateStr =
                  '${row.date!.year}-${row.date!.month.toString().padLeft(2, '0')}-${row.date!.day.toString().padLeft(2, '0')}';
              installments.add({'due_date': dateStr, 'amount': amountText});
            }
            Navigator.of(context).pop(installments);
          },
          child: Text(loc.translate('submit_request')),
        ),
      ],
    );
  }
}

class _InstallmentRow {
  DateTime? date;
  final TextEditingController amountController = TextEditingController();
}
