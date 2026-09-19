import 'package:flutter/material.dart';

import '../../../../core/utils/app_localizations.dart';

/// Small AppBar-action widget: a calendar icon that opens a month picker
/// when no filter is active, or an active-filter chip with a clear ("✕")
/// affordance once one is. Shared by ChargesScreen and PaymentHistoryScreen
/// so both get the exact same month-search behavior.
class MonthFilterBar extends StatelessWidget {
  final int? year;
  final int? month;
  final ValueChanged<DateTime?> onChanged;

  const MonthFilterBar({Key? key, this.year, this.month, required this.onChanged}) : super(key: key);

  Future<void> _pick(BuildContext context) async {
    final now = DateTime.now();
    final initial = (year != null && month != null) ? DateTime(year!, month!) : now;
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(now.year - 5),
      lastDate: DateTime(now.year, now.month + 1),
      helpText: AppLocalizations.of(context).translate('filter_by_month'),
    );
    if (picked != null) {
      onChanged(picked);
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final hasFilter = year != null && month != null;

    if (!hasFilter) {
      return IconButton(
        icon: const Icon(Icons.calendar_month_outlined),
        tooltip: loc.translate('filter_by_month'),
        onPressed: () => _pick(context),
      );
    }

    // A plain Container instead of InputChip: InputChip pulls its
    // background/label styling from the ambient Material chip theme (which
    // this app doesn't customize), and on a dark AppBar that rendered as a
    // solid white box with invisible white-on-white text — confirmed on a
    // real device. Full manual control here avoids that entirely.
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
      child: Material(
        color: Colors.white24,
        borderRadius: BorderRadius.circular(20),
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: () => _pick(context),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('$month/$year', style: const TextStyle(color: Colors.white, fontSize: 13)),
                const SizedBox(width: 4),
                InkWell(
                  onTap: () => onChanged(null),
                  child: const Icon(Icons.close, color: Colors.white, size: 16),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
