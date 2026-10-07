import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../auth/presentation/bloc/auth_state.dart';
import '../../../financial/presentation/bloc/clearance_bloc.dart';
import '../../../financial/presentation/bloc/financial_bloc.dart';
import '../../../financial/presentation/screens/clearance_screen.dart';
import '../../../financial/presentation/screens/payment_history_screen.dart';
import '../../../profile/presentation/screens/about_screen.dart';
import '../../../profile/presentation/screens/contact_us_screen.dart';
import '../../../profile/presentation/screens/payment_methods_screen.dart';
import '../../../profile/presentation/screens/profile_screen.dart';
import '../../../profile/presentation/screens/settings_screen.dart';
import '../../../profile/presentation/widgets/unit_labels.dart';

/// Shows the signed-in person — their name and role, and what identifies them
/// in the app: their unit (or how many units they have) and their village.
class AppDrawer extends StatelessWidget {
  const AppDrawer({Key? key}) : super(key: key);

  /// "Unit B1/101 · Delta Sharm", or "2 units · Delta Sharm" when they have several.
  static String _placeLine(AppLocalizations loc, AuthenticatedState state) {
    final units = state.units;
    final unitPart = units.isEmpty
        ? ''
        : units.length == 1
            ? '${loc.translate('unit')} ${units.first.unitKey}'
            : unitCountLabel(loc, units.length);
    return [unitPart, state.resortName].where((part) => part.isNotEmpty).join(' · ');
  }

  void _push(BuildContext context, Widget screen) {
    Navigator.of(context).pop();
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => screen));
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final authState = context.watch<AuthBloc>().state;
    final displayName = authState is AuthenticatedState ? authState.displayName : '';
    final placeLine = authState is AuthenticatedState ? _placeLine(loc, authState) : '';
    final logoUrl = authState is AuthenticatedState ? authState.resortLogoUrl : null;
    final roleLabel = authState is AuthenticatedState
        ? loc.translate(authState.role == 'TENANT' ? 'role_tenant' : 'role_owner')
        : '';

    return Drawer(
      backgroundColor: Colors.transparent,
      child: BackdropFilter(
        // Real frosted glass, not just a translucent color — and kept at
        // high opacity (per explicit request) so it reads as solid glass,
        // not a barely-there tint.
        filter: ImageFilter.blur(sigmaX: 26, sigmaY: 26),
        child: Container(
          color: AppColors.backgroundElevated.withOpacity(0.93),
          child: SafeArea(
            child: Column(
              children: [
                _DrawerHeader(displayName: displayName, roleLabel: roleLabel, placeLine: placeLine, logoUrl: logoUrl),
                Expanded(
                  child: ListView(
                    padding: EdgeInsets.zero,
                    children: [
                      ListTile(
                        leading: const Icon(Icons.person_outline),
                        title: Text(loc.translate('profile_title')),
                        onTap: () => _push(context, const ProfileScreen()),
                      ),
                      ListTile(
                        leading: const Icon(Icons.settings_outlined),
                        title: Text(loc.translate('settings_title')),
                        onTap: () => _push(context, const SettingsScreen()),
                      ),
                      ListTile(
                        leading: const Icon(Icons.credit_card_outlined),
                        title: Text(loc.translate('payment_methods_title')),
                        onTap: () => _push(context, const PaymentMethodsScreen()),
                      ),
                      ListTile(
                        leading: const Icon(Icons.receipt_long_outlined),
                        title: Text(loc.translate('payment_history_title')),
                        onTap: () => _push(context, const PaymentHistoryScreen()),
                      ),
                      ListTile(
                        leading: const Icon(Icons.fact_check_outlined),
                        title: Text(loc.translate('clearance_title')),
                        onTap: () {
                          // Resolved eagerly, before _push's Navigator.pop() runs —
                          // BlocProvider.create is lazy by default, so a closure that
                          // read from this drawer's own `context` instead would look
                          // up an ancestor on an already-deactivated widget the first
                          // time ClearanceScreen actually builds. Confirmed as a real
                          // crash on-device.
                          final financialRepository = context.read<FinancialBloc>().repository;
                          _push(
                            context,
                            BlocProvider(
                              create: (_) => ClearanceBloc(repository: financialRepository),
                              child: const ClearanceScreen(),
                            ),
                          );
                        },
                      ),
                      ListTile(
                        leading: const Icon(Icons.mail_outline),
                        title: Text(loc.translate('contact_us_title')),
                        onTap: () => _push(context, const ContactUsScreen()),
                      ),
                      ListTile(
                        leading: const Icon(Icons.info_outline),
                        title: Text(loc.translate('about_title')),
                        onTap: () => _push(context, const AboutScreen()),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DrawerHeader extends StatelessWidget {
  const _DrawerHeader({
    required this.displayName,
    required this.roleLabel,
    required this.placeLine,
    required this.logoUrl,
  });

  final String displayName;
  final String roleLabel;
  final String placeLine;
  final String? logoUrl;

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    return SizedBox(
      width: double.infinity,
      height: 232,
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (logoUrl != null)
            Image.network(
              logoUrl!,
              fit: BoxFit.cover,
              errorBuilder: (context, error, stackTrace) => const _HeaderFallback(),
            )
          else
            const _HeaderFallback(),
          // Scrim so the name stays legible over any photo.
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Colors.transparent, Color(0xB3000000)],
                stops: [0.4, 1],
              ),
            ),
          ),
          Positioned(
            left: 20,
            right: 20,
            bottom: 20,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  displayName.isNotEmpty ? displayName : loc.translate('app_title'),
                  style: const TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.bold),
                ),
                if (roleLabel.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(roleLabel, style: const TextStyle(color: Colors.white70, fontSize: 14)),
                  ),
                if (placeLine.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(
                      placeLine,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white70, fontSize: 14),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _HeaderFallback extends StatelessWidget {
  const _HeaderFallback();

  @override
  Widget build(BuildContext context) {
    return const DecoratedBox(
      decoration: BoxDecoration(gradient: AppColors.primaryGradient),
    );
  }
}
