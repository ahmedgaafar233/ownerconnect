import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TenantInterceptor extends Interceptor {
  final FlutterSecureStorage _storage;

  TenantInterceptor(this._storage);

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    // Set by FirebaseAuthRepository.fetchAndPersistProfile() right after
    // sign-in, from the authenticated user's own resort — never guessed or
    // defaulted here. No stored value means no header, which the backend's
    // TenantMiddleware treats as "no tenant" rather than resort 1.
    final resortId = await _storage.read(key: 'active_resort_id');
    if (resortId != null) {
      options.headers['X-Resort-ID'] = resortId;
    }
    handler.next(options);
  }
}
