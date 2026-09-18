import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../auth/presentation/bloc/auth_state.dart';
import '../../../profile/presentation/screens/about_screen.dart';
import '../../../profile/presentation/screens/contact_us_screen.dart';
import '../../../profile/presentation/screens/payment_methods_screen.dart';
import '../../../profile/presentation/screens/profile_screen.dart';
import '../../../profile/presentation/screens/settings_screen.dart';

/// The role label used to sit under the resort name in HomeShell's AppBar —
/// moved here (into the drawer header) since it looked bad pinned in the
/// AppBar permanently.
class AppDrawer extends StatelessWidget {
  const AppDrawer({Key? key}) : super(key: key);

  void _push(BuildContext context, Widget screen) {
    Navigator.of(context).pop();
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => screen));
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final authState = context.watch<AuthBloc>().state;
    final resortName = authState is AuthenticatedState ? authState.resortName : '';
    final roleLabel = authState is AuthenticatedState
        ? loc.translate(authState.role == 'TENANT' ? 'role_tenant' : 'role_owner')
        : '';

    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            DrawerHeader(
              decoration: const BoxDecoration(color: AppColors.primary),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text(
                    resortName.isNotEmpty ? resortName : loc.translate('app_title'),
                    style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  if (roleLabel.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(roleLabel, style: const TextStyle(color: Colors.white70, fontSize: 13)),
                    ),
                ],
              ),
            ),
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
    );
  }
}
