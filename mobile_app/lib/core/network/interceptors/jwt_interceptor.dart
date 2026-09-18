import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../constants/api_endpoints.dart';

/// JWT Authentication Interceptor.
///
/// Automatically attaches the Bearer token to every outgoing request.
/// On a 401 response, attempts a single token refresh then retries.
///
/// CRITICAL DESIGN: The token refresh call uses a dedicated [_refreshDio]
/// instance that does NOT have this interceptor attached. This prevents the
/// infinite 401 → refresh → 401 → refresh recursion that would occur if we
/// used the primary [_dio] instance (which carries this very interceptor).
class JwtInterceptor extends Interceptor {
  final FlutterSecureStorage _storage;
  final Dio _primaryDio;

  /// A plain Dio instance used exclusively for the /token/refresh/ call.
  /// It carries no interceptors, so a 401 from the refresh endpoint
  /// propagates as a normal DioException — not a recursive loop.
  late final Dio _refreshDio;

  /// Guards against concurrent refresh attempts when multiple requests
  /// fail with 401 simultaneously.
  bool _isRefreshing = false;
  final List<_PendingRequest> _pendingQueue = [];

  JwtInterceptor(this._storage, this._primaryDio) {
    final baseUrl =
        dotenv.env['API_BASE_URL'] ?? 'https://api.ownerconnect.com';

    _refreshDio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );
    // No interceptors are added to _refreshDio — this is intentional.
  }

  // ── onRequest ───────────────────────────────────────────────────────────────

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await _storage.read(key: 'access_token');
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  // ── onError ─────────────────────────────────────────────────────────────────

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode != 401) {
      // Not an auth error — pass through unchanged.
      handler.next(err);
      return;
    }

    final refreshToken = await _storage.read(key: 'refresh_token');
    if (refreshToken == null || refreshToken.isEmpty) {
      // No refresh token stored — user must log in again.
      await _clearCredentials();
      handler.next(err);
      return;
    }

    if (_isRefreshing) {
      // Another request is already refreshing.
      // Queue this request and resolve it once the refresh completes.
      final completer = Completer<Response<dynamic>>();
      _pendingQueue.add(_PendingRequest(err.requestOptions, completer));
      try {
        final response = await completer.future;
        handler.resolve(response);
      } catch (e) {
        handler.next(err);
      }
      return;
    }

    _isRefreshing = true;

    try {
      // ── Token refresh via the interceptor-free Dio instance ───────────────
      final refreshResponse = await _refreshDio.post(
        ApiEndpoints.tokenRefresh,
        data: {'refresh': refreshToken},
      );

      if (refreshResponse.statusCode == 200) {
        final newAccessToken = refreshResponse.data['access'] as String;
        final newRefreshToken = refreshResponse.data['refresh'] as String?;

        // Persist the new tokens
        await _storage.write(key: 'access_token', value: newAccessToken);
        if (newRefreshToken != null) {
          await _storage.write(key: 'refresh_token', value: newRefreshToken);
        }

        // Retry the original failed request with the new token
        final retryOptions = err.requestOptions;
        retryOptions.headers['Authorization'] = 'Bearer $newAccessToken';
        final retryResponse = await _primaryDio.fetch(retryOptions);

        // Resolve all queued requests with the new token
        for (final pending in _pendingQueue) {
          pending.requestOptions.headers['Authorization'] =
              'Bearer $newAccessToken';
          try {
            final queuedResponse =
                await _primaryDio.fetch(pending.requestOptions);
            pending.completer.complete(queuedResponse);
          } catch (e) {
            pending.completer.completeError(e);
          }
        }
        _pendingQueue.clear();

        handler.resolve(retryResponse);
      } else {
        // Refresh did not return 200 — clear credentials and propagate
        await _clearCredentials();
        _rejectPendingQueue(err);
        handler.next(err);
      }
    } on DioException catch (refreshErr) {
      // Refresh request itself failed (network error, 401, etc.)
      // A 401 here means the refresh token is invalid/expired — force logout.
      await _clearCredentials();
      _rejectPendingQueue(refreshErr);
      handler.next(err);
    } catch (unexpectedErr) {
      await _clearCredentials();
      _rejectPendingQueue(err);
      handler.next(err);
    } finally {
      _isRefreshing = false;
    }
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────

  Future<void> _clearCredentials() async {
    await _storage.deleteAll();
  }

  void _rejectPendingQueue(Object error) {
    for (final pending in _pendingQueue) {
      pending.completer.completeError(error);
    }
    _pendingQueue.clear();
  }
}

/// Internal holder for requests queued while a token refresh is in progress.
class _PendingRequest {
  final RequestOptions requestOptions;
  final Completer<Response<dynamic>> completer;

  const _PendingRequest(this.requestOptions, this.completer);
}
