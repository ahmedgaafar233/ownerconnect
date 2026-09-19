import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../data/models/charge_summary_model.dart';

class ChargeSummaryCard extends StatelessWidget {
  final ChargeSummaryModel summary;

  const ChargeSummaryCard({Key? key, required this.summary}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Card(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      color: AppColors.primary,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              loc.translate('combined_total'),
              style: const TextStyle(color: Colors.white70, fontSize: 13),
            ),
            const SizedBox(height: 4),
            Text(
              '${summary.totalRemaining.toStringAsFixed(2)} EGP',
              style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold),
            ),
            if (summary.byUnit.length > 1) ...[
              const Divider(color: Colors.white24, height: 24),
              Text(
                loc.translate('per_unit_breakdown'),
                style: const TextStyle(color: Colors.white70, fontSize: 12),
              ),
              const SizedBox(height: 8),
              ...summary.byUnit.map(
                (u) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(u.unitKey, style: const TextStyle(color: Colors.white, fontSize: 13)),
                      Text(
                        '${u.remaining.toStringAsFixed(2)} EGP',
                        style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
