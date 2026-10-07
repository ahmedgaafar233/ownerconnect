import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl_phone_field/intl_phone_field.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/utils/phone_utils.dart';
import '../../../../core/widgets/app_loading_indicator.dart';
import '../../data/models/payment_method_model.dart';
import '../../data/repositories/payment_method_repository.dart';
import '../bloc/payment_methods_bloc.dart';
import '../bloc/payment_methods_event.dart';
import '../bloc/payment_methods_state.dart';
import '../widgets/unit_labels.dart';

final _e164 = RegExp(r'^\+\d{8,15}$');
final _instapay = RegExp(r'^[A-Za-z0-9._-]{3,40}@[A-Za-z0-9]{2,25}$');

/// The person's saved ways to pay. Wallet, InstaPay and Fawry are saved here;
/// bank cards are not — card details only ever go into the payment provider's
/// own secure form, which opens once online payment goes live.
class PaymentMethodsScreen extends StatelessWidget {
  const PaymentMethodsScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          PaymentMethodsBloc(repository: context.read<PaymentMethodRepository>())..add(const PaymentMethodsLoadRequested()),
      child: const _PaymentMethodsView(),
    );
  }
}

class _PaymentMethodsView extends StatelessWidget {
  const _PaymentMethodsView();

  Future<void> _add(BuildContext context, PaymentMethodsLoadedState state) async {
    final bloc = context.read<PaymentMethodsBloc>();
    final event = await showModalBottomSheet<PaymentMethodAdded>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _AddMethodSheet(options: state.options),
    );
    if (event != null) bloc.add(event);
  }

  Future<void> _confirmRemove(BuildContext context, PaymentMethodModel method) async {
    final loc = AppLocalizations.of(context);
    final bloc = context.read<PaymentMethodsBloc>();
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(loc.translate('pm_remove')),
        content: Text(fillIn(loc.translate('pm_remove_confirm'), [method.label])),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: Text(loc.translate('cancel'))),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: Text(loc.translate('pm_remove')),
          ),
        ],
      ),
    );
    if (ok == true) bloc.add(PaymentMethodRemoved(method.id));
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('payment_methods_title'))),
      body: BlocConsumer<PaymentMethodsBloc, PaymentMethodsState>(
        listener: (context, state) {
          if (state is! PaymentMethodsLoadedState) return;
          final messenger = ScaffoldMessenger.of(context);
          if (state.error != null) {
            messenger.showSnackBar(SnackBar(content: Text(state.error!), backgroundColor: AppColors.error));
          } else if (state.notice != null) {
            messenger.showSnackBar(SnackBar(content: Text(loc.translate('pm_${state.notice}'))));
          }
        },
        builder: (context, state) {
          if (state is PaymentMethodsLoadingState) return const Center(child: AppLoadingIndicator());
          if (state is PaymentMethodsErrorState) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(state.message, textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    OutlinedButton(
                      onPressed: () => context.read<PaymentMethodsBloc>().add(const PaymentMethodsLoadRequested()),
                      child: Text(loc.translate('retry_button')),
                    ),
                  ],
                ),
              ),
            );
          }

          final loaded = state as PaymentMethodsLoadedState;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(loc.translate('pm_intro'), style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
              const SizedBox(height: 16),
              if (loaded.methods.isEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 32),
                  child: Column(
                    children: [
                      const Icon(Icons.account_balance_wallet_outlined, size: 48, color: AppColors.textTertiary),
                      const SizedBox(height: 12),
                      Text(loc.translate('pm_empty'), style: const TextStyle(color: AppColors.textSecondary)),
                    ],
                  ),
                )
              else
                for (final method in loaded.methods)
                  _MethodTile(
                    method: method,
                    busy: loaded.isBusy,
                    onMakeDefault: () => context.read<PaymentMethodsBloc>().add(PaymentMethodMadeDefault(method.id)),
                    onRemove: () => _confirmRemove(context, method),
                  ),
              const SizedBox(height: 16),
              if (loaded.isFull)
                Text(loc.translate('pm_full'), style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
              ElevatedButton.icon(
                onPressed: loaded.isBusy || loaded.isFull ? null : () => _add(context, loaded),
                icon: loaded.isBusy
                    ? const AppLoadingIndicator(size: 18, strokeWidth: 2)
                    : const Icon(Icons.add),
                label: Text(loc.translate('pm_add')),
              ),
            ],
          );
        },
      ),
    );
  }
}

IconData _iconFor(String kind) => switch (kind) {
      'CARD' => Icons.credit_card,
      'WALLET' => Icons.account_balance_wallet_outlined,
      'INSTAPAY' => Icons.swap_horiz,
      _ => Icons.storefront_outlined,
    };

class _MethodTile extends StatelessWidget {
  const _MethodTile({required this.method, required this.busy, required this.onMakeDefault, required this.onRemove});

  final PaymentMethodModel method;
  final bool busy;
  final VoidCallback onMakeDefault;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsetsDirectional.only(start: 14, end: 4, top: 6, bottom: 6),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: method.isDefault ? AppColors.primary : AppColors.border),
      ),
      child: Row(
        children: [
          Icon(_iconFor(method.kind), color: AppColors.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(method.label, style: const TextStyle(fontWeight: FontWeight.w600)),
                if (method.isDefault)
                  Text(
                    loc.translate('pm_default'),
                    style: const TextStyle(color: AppColors.primary, fontSize: 12, fontWeight: FontWeight.w700),
                  ),
              ],
            ),
          ),
          PopupMenuButton<String>(
            enabled: !busy,
            onSelected: (value) => value == 'default' ? onMakeDefault() : onRemove(),
            itemBuilder: (_) => [
              if (!method.isDefault) PopupMenuItem(value: 'default', child: Text(loc.translate('pm_make_default'))),
              PopupMenuItem(value: 'remove', child: Text(loc.translate('pm_remove'))),
            ],
          ),
        ],
      ),
    );
  }
}

/// Pick what to add, then fill in what it needs. Returns the event to run, or
/// null if dismissed. Bank cards are listed but not offered: they go through
/// the payment provider's secure form, which isn't live yet.
class _AddMethodSheet extends StatefulWidget {
  const _AddMethodSheet({required this.options});

  final PaymentMethodOptions options;

  @override
  State<_AddMethodSheet> createState() => _AddMethodSheetState();
}

class _AddMethodSheetState extends State<_AddMethodSheet> {
  String? _kind; // null = still choosing
  String? _provider;
  String _phone = '';
  final _address = TextEditingController();

  @override
  void initState() {
    super.initState();
    _address.addListener(() => setState(() {}));
    if (widget.options.walletProviders.isNotEmpty) _provider = widget.options.walletProviders.first.value;
  }

  @override
  void dispose() {
    _address.dispose();
    super.dispose();
  }

  bool get _canSave => switch (_kind) {
        'WALLET' => _provider != null && _e164.hasMatch(_phone),
        'INSTAPAY' => _instapay.hasMatch(_address.text.trim()),
        'FAWRY' => true,
        _ => false,
      };

  void _save() {
    if (!_canSave) return;
    Navigator.of(context).pop(PaymentMethodAdded(
      kind: _kind!,
      walletProvider: _kind == 'WALLET' ? _provider : null,
      walletPhone: _kind == 'WALLET' ? _phone : null,
      instapayAddress: _kind == 'INSTAPAY' ? _address.text.trim() : null,
    ));
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(loc.translate('pm_add'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            if (_kind == null) ...[
              // A bank card: shown so people know where it will be, but never entered here.
              ListTile(
                enabled: false,
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.credit_card),
                title: Text(loc.translate('pm_card')),
                subtitle: Text(loc.translate('pm_card_soon')),
                trailing: const Icon(Icons.lock_outline, size: 18),
              ),
              const Divider(),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.account_balance_wallet_outlined, color: AppColors.primary),
                title: Text(loc.translate('pm_wallet')),
                subtitle: Text(loc.translate('pm_wallet_hint')),
                onTap: () => setState(() => _kind = 'WALLET'),
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.swap_horiz, color: AppColors.primary),
                title: Text(loc.translate('pm_instapay')),
                subtitle: Text(loc.translate('pm_instapay_hint')),
                onTap: () => setState(() => _kind = 'INSTAPAY'),
              ),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.storefront_outlined, color: AppColors.primary),
                title: Text(loc.translate('pm_fawry')),
                subtitle: Text(loc.translate('pm_fawry_hint')),
                onTap: () => setState(() => _kind = 'FAWRY'),
              ),
            ] else ...[
              if (_kind == 'WALLET') ...[
                Text(loc.translate('pm_wallet_provider'), style: const TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final provider in widget.options.walletProviders)
                      ChoiceChip(
                        label: Text(provider.label),
                        selected: _provider == provider.value,
                        onSelected: (_) => setState(() => _provider = provider.value),
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                IntlPhoneField(
                  decoration: InputDecoration(labelText: loc.translate('pm_wallet_phone'), counterText: ''),
                  initialCountryCode: 'EG',
                  onChanged: (phone) => setState(() => _phone = normalizedCompleteNumber(phone)),
                ),
              ] else if (_kind == 'INSTAPAY')
                TextField(
                  controller: _address,
                  keyboardType: TextInputType.emailAddress,
                  autocorrect: false,
                  decoration: InputDecoration(labelText: loc.translate('pm_instapay_address')),
                )
              else
                Text(loc.translate('pm_fawry_hint'), style: const TextStyle(color: AppColors.textSecondary)),
              const SizedBox(height: 16),
              // Stacked, not side by side: the app's buttons are full width, and a
              // full-width button can't sit in a Row.
              ElevatedButton(onPressed: _canSave ? _save : null, child: Text(loc.translate('save_button'))),
              const SizedBox(height: 4),
              Center(
                child: TextButton(onPressed: () => setState(() => _kind = null), child: Text(loc.translate('cancel'))),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
