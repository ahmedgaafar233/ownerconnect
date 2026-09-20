import 'package:dio/dio.dart';

import '../../../../core/constants/api_endpoints.dart';
import '../models/resort_model.dart';

class ResortRepository {
  final Dio dio;

  ResortRepository({required this.dio});

  /// Public endpoint, no auth required — the resort picker runs before login.
  Future<List<ResortModel>> getResorts() async {
    final response = await dio.get(ApiEndpoints.resorts);
    final results = response.data as List;
    return results.map((e) => ResortModel.fromJson(e as Map<String, dynamic>)).toList();
  }
}
