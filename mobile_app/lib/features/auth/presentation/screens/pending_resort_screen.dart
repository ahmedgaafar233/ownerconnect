import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../bloc/auth_bloc.dart';
import '../bloc/auth_event.dart';

/// Shown when the backend confirms the user is signed in but `resort` is
/// still null — the account exists but no admin has linked it to a village
/// yet. Deliberately has no way forward except logout: there is nothing
/// useful the app can show without a resort to scope data to.
class PendingResortScreen extends StatelessWidget {
  const PendingResortScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.hourglass_empty, size: 64, color: AppColors.textSecondary),
              const SizedBox(height: 24),
              Text(
                loc.translate('pending_resort_title'),
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
              ),
              const SizedBox(height: 12),
              Text(
                loc.translate('pending_resort_message'),
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 14, color: AppColors.textSecondary),
              ),
              const SizedBox(height: 32),
              OutlinedButton(
                onPressed: () => context.read<AuthBloc>().add(const LogoutRequested()),
                child: Text(loc.translate('logout')),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
