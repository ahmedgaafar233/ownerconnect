import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/widgets/owc_mark.dart';
import '../../data/resort_selection.dart';

/// Brief branded welcome right after picking a resort in ResortPickerScreen
/// — shows that resort's own logo/name rather than the generic OwnerConnect
/// mark, then continues on to login by itself (or immediately, if tapped).
class ResortWelcomeScreen extends StatefulWidget {
  const ResortWelcomeScreen({Key? key}) : super(key: key);

  @override
  State<ResortWelcomeScreen> createState() => _ResortWelcomeScreenState();
}

class _ResortWelcomeScreenState extends State<ResortWelcomeScreen> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer(const Duration(milliseconds: 1800), _continue);
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _continue() {
    if (mounted) context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final resort = context.watch<ResortSelection>().value;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: _continue,
        child: SafeArea(
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(28),
                  child: SizedBox(
                    width: 120,
                    height: 120,
                    child: resort?.logoUrl != null
                        ? Image.network(
                            resort!.logoUrl!,
                            fit: BoxFit.cover,
                            errorBuilder: (context, error, stackTrace) => const OwcMark(size: 120),
                          )
                        : const OwcMark(size: 120),
                  ),
                ),
                const SizedBox(height: 28),
                Text(
                  loc.translate('welcome_to_resort'),
                  style: const TextStyle(fontSize: 15, color: AppColors.textSecondary, fontWeight: FontWeight.w500),
                ),
                const SizedBox(height: 4),
                Text(
                  resort?.name ?? '',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                ),
                const SizedBox(height: 10),
                Text(
                  loc.translate('welcome_resort_subtitle'),
                  style: const TextStyle(fontSize: 14, color: AppColors.textTertiary),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
