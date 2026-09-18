import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/localization/locale_cubit.dart';
import '../../../../core/utils/app_localizations.dart';

class LanguageScreen extends StatelessWidget {
  const LanguageScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final currentCode = context.watch<LocaleCubit>().state.languageCode;

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('language_title'))),
      body: Column(
        children: [
          RadioListTile<String>(
            title: const Text('English'),
            value: 'en',
            groupValue: currentCode,
            onChanged: (code) => context.read<LocaleCubit>().setLocale(code!),
          ),
          RadioListTile<String>(
            title: const Text('العربية'),
            value: 'ar',
            groupValue: currentCode,
            onChanged: (code) => context.read<LocaleCubit>().setLocale(code!),
          ),
        ],
      ),
    );
  }
}
