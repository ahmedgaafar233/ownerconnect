import 'package:flutter/material.dart';

import '../../../../core/utils/app_localizations.dart';

/// "1 unit" / "2 units" / "5 units" — the language's own plural form.
String unitCountLabel(AppLocalizations loc, int count) {
  if (count == 1) return loc.translate('unit_count_one');
  if (count == 2) return loc.translate('unit_count_two');
  return loc.translate('unit_count_many').replaceFirst('%d', '$count');
}

/// A yyyy-MM-dd date from the server, written the way this language writes dates.
String formatServerDate(BuildContext context, String ymd) {
  final date = DateTime.tryParse(ymd);
  return date == null ? ymd : MaterialLocalizations.of(context).formatMediumDate(date);
}

/// Fills the `%s` placeholders of a translated sentence, in order.
String fillIn(String template, List<String> values) {
  var result = template;
  for (final value in values) {
    result = result.replaceFirst('%s', value);
  }
  return result;
}
