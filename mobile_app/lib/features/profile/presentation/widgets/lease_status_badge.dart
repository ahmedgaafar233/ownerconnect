import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';

/// ACTIVE / UPCOMING / ENDED pill for a rental.
class LeaseStatusBadge extends StatelessWidget {
  const LeaseStatusBadge({Key? key, required this.status}) : super(key: key);

  final String status;

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final (Color color, String labelKey) = switch (status) {
      'UPCOMING' => (AppColors.warning, 'rent_status_upcoming'),
      'ENDED' || 'CANCELLED' => (AppColors.textSecondary, 'rent_status_ended'),
      _ => (AppColors.success, 'rent_status_active'),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        loc.translate(labelKey),
        style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w700),
      ),
    );
  }
}
