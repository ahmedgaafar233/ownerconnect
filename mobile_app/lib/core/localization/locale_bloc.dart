import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../utils/app_localizations.dart';
import 'locale_event.dart';
import 'locale_state.dart';

const _localePreferenceKey = 'locale_preference';

/// Persists the chosen app language the same way access_token/active_resort_id
/// already are (FlutterSecureStorage is the only local-persistence mechanism
/// used anywhere in this app — no SharedPreferences dependency exists, so
/// this reuses it instead of adding a second one just for one string).
class LocaleBloc extends Bloc<LocaleEvent, LocaleState> {
  final FlutterSecureStorage _storage;

  LocaleBloc({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage(),
        super(const LocaleState(Locale('en'))) {
    on<LocaleLoadRequested>(_onLoadRequested);
    on<LocaleChanged>(_onChanged);
  }

  Future<void> _onLoadRequested(LocaleLoadRequested event, Emitter<LocaleState> emit) async {
    final saved = await _storage.read(key: _localePreferenceKey);
    if (saved != null && saved.isNotEmpty) {
      emit(LocaleState(Locale(saved)));
      return;
    }
    emit(LocaleState(Locale(_resolveDeviceLanguageCode())));
  }

  Future<void> _onChanged(LocaleChanged event, Emitter<LocaleState> emit) async {
    await _storage.write(key: _localePreferenceKey, value: event.languageCode);
    emit(LocaleState(Locale(event.languageCode)));
  }

  /// The device's own system language if this app ships a full translation
  /// for it, otherwise English — never assume Arabic just because this
  /// project started in Egypt; most owners are not Arabic or English
  /// speakers.
  String _resolveDeviceLanguageCode() {
    final deviceLocales = WidgetsBinding.instance.platformDispatcher.locales;
    for (final deviceLocale in deviceLocales) {
      for (final supported in kSupportedLocales) {
        if (supported.languageCode == deviceLocale.languageCode) {
          return supported.languageCode;
        }
      }
    }
    return 'en';
  }
}
