import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _localePreferenceKey = 'locale_preference';

/// Persists the chosen app language the same way access_token/active_resort_id
/// already are (FlutterSecureStorage is the only local-persistence mechanism
/// used anywhere in this app — no SharedPreferences dependency exists, so
/// this reuses it instead of adding a second one just for one string).
class LocaleCubit extends Cubit<Locale> {
  final FlutterSecureStorage _storage;

  LocaleCubit({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage(),
        super(const Locale('ar'));

  Future<void> load() async {
    final saved = await _storage.read(key: _localePreferenceKey);
    if (saved != null && saved.isNotEmpty) {
      emit(Locale(saved));
    }
  }

  Future<void> setLocale(String languageCode) async {
    await _storage.write(key: _localePreferenceKey, value: languageCode);
    emit(Locale(languageCode));
  }
}
