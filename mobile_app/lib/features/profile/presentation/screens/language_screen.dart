import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/localization/locale_bloc.dart';
import '../../../../core/localization/locale_event.dart';
import '../../../../core/utils/app_localizations.dart';

const _languageNames = <String, String>{
  'en': 'English',
  'ar': 'العربية',
  'de': 'Deutsch',
  'fr': 'Français',
  'it': 'Italiano',
  'ru': 'Русский',
  'uk': 'Українська',
  'fi': 'Suomi',
  'nb': 'Norsk',
  'zh': '中文',
  'hi': 'हिन्दी',
  'ja': '日本語',
};

class LanguageScreen extends StatelessWidget {
  const LanguageScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final currentCode = context.watch<LocaleBloc>().state.locale.languageCode;

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('language_title'))),
      body: ListView(
        children: kSupportedLocales.map((locale) {
          final code = locale.languageCode;
          return RadioListTile<String>(
            title: Text(_languageNames[code] ?? code),
            value: code,
            groupValue: currentCode,
            onChanged: (value) => context.read<LocaleBloc>().add(LocaleChanged(value!)),
          );
        }).toList(),
      ),
    );
  }
}
