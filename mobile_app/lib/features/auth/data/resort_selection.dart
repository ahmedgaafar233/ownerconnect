import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'models/resort_model.dart';

const _idKey = 'selected_resort_id';
const _nameKey = 'selected_resort_name';
const _logoKey = 'selected_resort_logo_url';

/// Which resort the owner picked on first launch — purely local branding
/// state for the pre-login welcome screen. This is NOT a tenant switch: the
/// backend already knows a signed-in user's resort from their account,
/// independent of whatever was picked here. A ValueNotifier (not a full
/// Bloc) because its only job is to gate one redirect decision in
/// AppRouter, which needs a Listenable it can merge into refreshListenable.
class ResortSelection extends ValueNotifier<ResortModel?> {
  final FlutterSecureStorage _storage;

  ResortSelection(this._storage, ResortModel? initial) : super(initial);

  static Future<ResortSelection> load({FlutterSecureStorage? storage}) async {
    final s = storage ?? const FlutterSecureStorage();
    // Each secure-storage read is a slow Android keystore round trip — three
    // in a row was a noticeable slice of start-up, so they run together.
    final values = await Future.wait([s.read(key: _idKey), s.read(key: _nameKey), s.read(key: _logoKey)]);
    final id = values[0], name = values[1], logo = values[2];
    if (id == null || name == null) return ResortSelection(s, null);
    return ResortSelection(s, ResortModel(id: int.parse(id), name: name, logoUrl: logo));
  }

  Future<void> select(ResortModel resort) async {
    await _storage.write(key: _idKey, value: resort.id.toString());
    await _storage.write(key: _nameKey, value: resort.name);
    if (resort.logoUrl != null) {
      await _storage.write(key: _logoKey, value: resort.logoUrl);
    } else {
      await _storage.delete(key: _logoKey);
    }
    value = resort;
  }
}
