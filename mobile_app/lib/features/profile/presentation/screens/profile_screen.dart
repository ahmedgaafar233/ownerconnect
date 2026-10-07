import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/widgets/app_loading_indicator.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../auth/presentation/bloc/auth_event.dart';
import '../../../financial/presentation/bloc/financial_bloc.dart';
import '../../../financial/presentation/bloc/financial_event.dart';
import '../../data/models/profile_unit.dart';
import '../../data/repositories/lease_repository.dart';
import '../bloc/lease_bloc.dart';
import '../bloc/profile_bloc.dart';
import '../bloc/profile_event.dart';
import '../bloc/profile_state.dart';
import '../widgets/profile_unit_card.dart';
import '../widgets/unit_labels.dart';
import 'lease_details_screen.dart';
import 'rent_out_screen.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (context) =>
          ProfileBloc(repository: context.read<AuthBloc>().repository)..add(const ProfileLoadRequested()),
      child: const _ProfileView(),
    );
  }
}

class _ProfileView extends StatelessWidget {
  const _ProfileView();

  /// A rental was registered or ended: everything that mirrors it has to
  /// follow — this screen, the drawer's header, and the owner's own charges
  /// (the utility months that moved away, or came back, change that list).
  void _afterLeaseChange(BuildContext context) {
    context.read<ProfileBloc>().add(const ProfileLoadRequested(refresh: true));
    context.read<AuthBloc>().add(const ProfileRefreshRequested());
    context.read<FinancialBloc>()
      ..add(const FetchChargesEvent(page: 1))
      ..add(const FetchChargeSummaryEvent());
  }

  Future<void> _openRentOut(BuildContext context, ProfileUnit unit) async {
    // Read now, before the route is pushed — see the clearance entry in the drawer.
    final repository = context.read<LeaseRepository>();
    final changed = await Navigator.of(context).push<bool>(MaterialPageRoute(
      builder: (_) => BlocProvider(
        create: (_) => LeaseBloc(repository: repository),
        child: RentOutScreen(unit: unit),
      ),
    ));
    if (changed == true && context.mounted) _afterLeaseChange(context);
  }

  Future<void> _openLease(BuildContext context, ProfileUnit unit) async {
    final repository = context.read<LeaseRepository>();
    final changed = await Navigator.of(context).push<bool>(MaterialPageRoute(
      builder: (_) => BlocProvider(
        create: (_) => LeaseBloc(repository: repository),
        child: LeaseDetailsScreen(unit: unit, lease: unit.lease!),
      ),
    ));
    if (changed == true && context.mounted) _afterLeaseChange(context);
  }

  Future<void> _editName(BuildContext context, ProfileLoadedState profile) async {
    final bloc = context.read<ProfileBloc>();
    final name = await showDialog<String>(
      context: context,
      builder: (_) => _EditNameDialog(initial: profile.fullname),
    );
    if (name != null) bloc.add(ProfileNameSaved(name));
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('profile_title'))),
      body: BlocConsumer<ProfileBloc, ProfileState>(
        listener: (context, state) {
          if (state is! ProfileLoadedState) return;
          if (state.justSaved) {
            // The drawer reads the name from the signed-in state, not from
            // this screen — tell it, or it keeps showing the old one.
            context.read<AuthBloc>().add(const ProfileRefreshRequested());
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(loc.translate('profile_saved'))));
          } else if (state.saveError != null) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.saveError!), backgroundColor: AppColors.error),
            );
          }
        },
        builder: (context, state) {
          if (state is ProfileLoadingState) {
            return const Center(child: AppLoadingIndicator());
          }
          if (state is ProfileErrorState) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(state.message, textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    OutlinedButton(
                      onPressed: () => context.read<ProfileBloc>().add(const ProfileLoadRequested()),
                      child: Text(loc.translate('retry_button')),
                    ),
                  ],
                ),
              ),
            );
          }

          final profile = state as ProfileLoadedState;
          return RefreshIndicator(
            onRefresh: () async {
              context.read<ProfileBloc>().add(const ProfileLoadRequested(refresh: true));
            },
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              children: [
                _IdentityCard(profile: profile, onEdit: () => _editName(context, profile)),
                const SizedBox(height: 12),
                _InfoRow(icon: Icons.phone_outlined, label: loc.translate('phone_hint'), value: profile.phone),
                _InfoRow(
                  icon: Icons.holiday_village_outlined,
                  label: loc.translate('village_label'),
                  value: profile.resortName.isEmpty ? '-' : profile.resortName,
                ),
                const SizedBox(height: 20),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        loc.translate('profile_my_units'),
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                      ),
                    ),
                    if (profile.units.isNotEmpty)
                      Text(
                        unitCountLabel(loc, profile.units.length),
                        style: const TextStyle(color: AppColors.textSecondary),
                      ),
                  ],
                ),
                const SizedBox(height: 12),
                if (profile.units.isEmpty)
                  Text(loc.translate('profile_no_units'), style: const TextStyle(color: AppColors.textSecondary))
                else
                  for (final unit in profile.units)
                    ProfileUnitCard(
                      unit: unit,
                      onRentOut: () => _openRentOut(context, unit),
                      onOpenLease: () => _openLease(context, unit),
                    ),
              ],
            ),
          );
        },
      ),
    );
  }
}

/// Who this person is: initials, name, role — with the village and unit(s)
/// below it in the cards that follow.
class _IdentityCard extends StatelessWidget {
  const _IdentityCard({required this.profile, required this.onEdit});

  final ProfileLoadedState profile;
  final VoidCallback onEdit;

  String get _initials {
    final words = profile.fullname.trim().split(RegExp(r'\s+')).where((w) => w.isNotEmpty).toList();
    if (words.isEmpty) return '';
    return words.take(2).map((w) => String.fromCharCode(w.runes.first).toUpperCase()).join();
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final initials = _initials;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border),
      ),
      child: Row(
        children: [
          Container(
            width: 64,
            height: 64,
            alignment: Alignment.center,
            decoration: const BoxDecoration(shape: BoxShape.circle, gradient: AppColors.primaryGradient),
            child: initials.isEmpty
                ? const Icon(Icons.person, color: Colors.white, size: 32)
                : Text(initials, style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w700)),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  profile.displayName,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.glassFill,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    loc.translate(profile.isTenant ? 'role_tenant' : 'role_owner'),
                    style: const TextStyle(color: AppColors.primaryDeep, fontWeight: FontWeight.w600, fontSize: 12),
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: loc.translate('profile_edit_name'),
            onPressed: profile.isSaving ? null : onEdit,
            icon: profile.isSaving
                ? const AppLoadingIndicator(size: 20, strokeWidth: 2)
                : const Icon(Icons.edit_outlined),
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.label, required this.value});

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child: Row(
        children: [
          Icon(icon, size: 20, color: AppColors.textSecondary),
          const SizedBox(width: 12),
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

class _EditNameDialog extends StatefulWidget {
  const _EditNameDialog({required this.initial});

  final String initial;

  @override
  State<_EditNameDialog> createState() => _EditNameDialogState();
}

class _EditNameDialogState extends State<_EditNameDialog> {
  late final TextEditingController _controller = TextEditingController(text: widget.initial);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    return AlertDialog(
      title: Text(loc.translate('profile_edit_name')),
      content: TextField(
        controller: _controller,
        autofocus: true,
        textCapitalization: TextCapitalization.words,
        decoration: InputDecoration(labelText: loc.translate('fullname_hint')),
        onChanged: (_) => setState(() {}),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: Text(loc.translate('cancel'))),
        TextButton(
          onPressed: _controller.text.trim().isEmpty ? null : () => Navigator.of(context).pop(_controller.text.trim()),
          child: Text(loc.translate('save_button')),
        ),
      ],
    );
  }
}
