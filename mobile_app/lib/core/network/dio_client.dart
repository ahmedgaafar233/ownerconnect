import 'package:dio/dio.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'interceptors/jwt_interceptor.dart';
import 'interceptors/tenant_interceptor.dart';

class DioClient {
  late final Dio dio;
  final FlutterSecureStorage storage = const FlutterSecureStorage();

  DioClient() {
    final baseUrl = dotenv.env['API_BASE_URL'] ?? 'https://api.ownerconnect.com';
    dio = Dio(
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

    dio.interceptors.addAll([
      TenantInterceptor(storage),
      JwtInterceptor(storage, dio),
      LogInterceptor(
        requestBody: true,
        responseBody: true,
      ),
    ]);
  }
}
