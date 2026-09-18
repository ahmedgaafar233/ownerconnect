import 'package:flutter/material.dart';

import '../../../../core/utils/app_localizations.dart';
import 'language_screen.dart';

/// Just hosts Language for now — room to grow as real settings (not fake
/// toggles for things that don't exist yet) get added.
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('settings_title'))),
      body: ListView(
        children: [
          ListTile(
            leading: const Icon(Icons.language),
            title: Text(loc.translate('language_title')),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const LanguageScreen()),
            ),
          ),
        ],
      ),
    );
  }
}
