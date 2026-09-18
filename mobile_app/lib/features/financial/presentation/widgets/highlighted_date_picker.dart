import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';

/// A month-grid date picker that, unlike the stock Material [showDatePicker]
/// (which only distinguishes "today" and "selected"), also marks the day a
/// charge was issued in its own color — the app has no other way to show
/// the owner "here's when the debt started" next to "here's today" and
/// "here's the day you're picking" at a glance.
Future<DateTime?> showHighlightedDatePicker({
  required BuildContext context,
  required DateTime firstDate,
  required DateTime lastDate,
  required DateTime initialDate,
  DateTime? chargeIssuedDate,
}) {
  return showDialog<DateTime>(
    context: context,
    builder: (_) => _HighlightedDatePickerDialog(
      firstDate: firstDate,
      lastDate: lastDate,
      initialDate: initialDate,
      chargeIssuedDate: chargeIssuedDate,
    ),
  );
}

class _HighlightedDatePickerDialog extends StatefulWidget {
  final DateTime firstDate;
  final DateTime lastDate;
  final DateTime initialDate;
  final DateTime? chargeIssuedDate;

  const _HighlightedDatePickerDialog({
    required this.firstDate,
    required this.lastDate,
    required this.initialDate,
    this.chargeIssuedDate,
  });

  @override
  State<_HighlightedDatePickerDialog> createState() => _HighlightedDatePickerDialogState();
}

class _HighlightedDatePickerDialogState extends State<_HighlightedDatePickerDialog> {
  late DateTime _visibleMonth;
  DateTime? _selected;

  bool _isSameDay(DateTime a, DateTime b) => a.year == b.year && a.month == b.month && a.day == b.day;

  @override
  void initState() {
    super.initState();
    _visibleMonth = DateTime(widget.initialDate.year, widget.initialDate.month);
  }

  void _changeMonth(int delta) {
    setState(() => _visibleMonth = DateTime(_visibleMonth.year, _visibleMonth.month + delta));
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final today = DateTime.now();
    final firstWeekday = DateTime(_visibleMonth.year, _visibleMonth.month, 1).weekday % 7;
    final daysInMonth = DateTime(_visibleMonth.year, _visibleMonth.month + 1, 0).day;

    return AlertDialog(
      contentPadding: const EdgeInsets.all(16),
      content: SizedBox(
        width: 320,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                IconButton(icon: const Icon(Icons.chevron_left), onPressed: () => _changeMonth(-1)),
                Text(
                  '${_visibleMonth.year}-${_visibleMonth.month.toString().padLeft(2, '0')}',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                IconButton(icon: const Icon(Icons.chevron_right), onPressed: () => _changeMonth(1)),
              ],
            ),
            const SizedBox(height: 8),
            GridView.count(
              crossAxisCount: 7,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              children: [
                for (var i = 0; i < firstWeekday; i++) const SizedBox.shrink(),
                for (var day = 1; day <= daysInMonth; day++) _buildDay(day, today),
              ],
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 12,
              children: [
                _legendDot(AppColors.accent, loc.translate('legend_issued')),
                _legendDot(AppColors.primary, loc.translate('legend_today')),
                _legendDot(AppColors.success, loc.translate('legend_selected')),
              ],
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: Text(loc.translate('cancel'))),
        ElevatedButton(
          onPressed: _selected == null ? null : () => Navigator.of(context).pop(_selected),
          child: Text(loc.translate('pick_date')),
        ),
      ],
    );
  }

  Widget _buildDay(int day, DateTime today) {
    final date = DateTime(_visibleMonth.year, _visibleMonth.month, day);
    final inRange = !date.isBefore(widget.firstDate) && !date.isAfter(widget.lastDate);
    final isToday = _isSameDay(date, today);
    final isIssued = widget.chargeIssuedDate != null && _isSameDay(date, widget.chargeIssuedDate!);
    final isSelected = _selected != null && _isSameDay(date, _selected!);

    Color? bg;
    Color fg = AppColors.textPrimary;
    if (isSelected) {
      bg = AppColors.success;
      fg = Colors.white;
    } else if (isIssued) {
      bg = AppColors.accent;
      fg = Colors.white;
    } else if (isToday) {
      bg = AppColors.primary.withOpacity(0.15);
    }

    return Padding(
      padding: const EdgeInsets.all(2),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: inRange ? () => setState(() => _selected = date) : null,
        child: Container(
          decoration: BoxDecoration(
            color: bg,
            shape: BoxShape.circle,
            border: isToday && !isSelected ? Border.all(color: AppColors.primary, width: 1.5) : null,
          ),
          alignment: Alignment.center,
          child: Text(
            '$day',
            style: TextStyle(color: inRange ? fg : AppColors.textSecondary.withOpacity(0.4)),
          ),
        ),
      ),
    );
  }

  Widget _legendDot(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 10, height: 10, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11)),
      ],
    );
  }
}
