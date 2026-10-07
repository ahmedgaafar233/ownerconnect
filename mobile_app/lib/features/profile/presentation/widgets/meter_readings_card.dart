import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../data/models/lease_model.dart';
import 'unit_labels.dart';

/// The electricity and water readings Maintenance took at entry and exit —
/// "Not read yet" until they have. Reference only: they don't change the bills.
class MeterReadingsCard extends StatelessWidget {
  const MeterReadingsCard({Key? key, required this.readings, this.showExit = true}) : super(key: key);

  final Map<String, MeterPair> readings;

  /// A tenant's own copy leaves the exit reading out while they're still living there.
  final bool showExit;

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    const meters = [('ELECTRICITY', 'meter_electricity', Icons.bolt_outlined), ('WATER', 'meter_water', Icons.water_drop_outlined)];

    String describe(MeterReadingValue? value) => value == null
        ? loc.translate('meter_pending')
        : '${value.reading} · ${formatServerDate(context, value.readOn)}';

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final (meter, labelKey, icon) in meters) ...[
            Row(
              children: [
                Icon(icon, size: 20, color: AppColors.primary),
                const SizedBox(width: 8),
                Text(loc.translate(labelKey), style: const TextStyle(fontWeight: FontWeight.w700)),
              ],
            ),
            const SizedBox(height: 6),
            _Line(label: loc.translate('meter_entry'), value: describe(readings[meter]?.entry)),
            if (showExit) _Line(label: loc.translate('meter_exit'), value: describe(readings[meter]?.exit)),
            const SizedBox(height: 10),
          ],
          Text(loc.translate('meter_hint'), style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}

class _Line extends StatelessWidget {
  const _Line({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsetsDirectional.only(start: 28, bottom: 2),
      child: Row(
        children: [
          Text(label, style: const TextStyle(color: AppColors.textSecondary)),
          const SizedBox(width: 12),
          Expanded(child: Text(value, textAlign: TextAlign.end, style: const TextStyle(fontWeight: FontWeight.w600))),
        ],
      ),
    );
  }
}
