import 'package:dio/dio.dart';
import '../../../../core/constants/api_endpoints.dart';
import '../models/charge_model.dart';

class FinancialRepository {
  final Dio dio;

  FinancialRepository({required this.dio});

  Future<List<ChargeModel>> getCharges({int page = 1, String? type, bool? unpaidOnly}) async {
    final queryParams = <String, dynamic>{
      'page': page,
    };
    if (type != null && type.isNotEmpty) {
      queryParams['type'] = type;
    }
    if (unpaidOnly == true) {
      queryParams['unpaid_only'] = 'true';
    }

    final response = await dio.get(
      ApiEndpoints.charges,
      queryParameters: queryParams,
    );

    final results = response.data['results'] as List;
    return results.map((e) => ChargeModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> initiateOnlinePayment(List<int> chargeIds) async {
    final response = await dio.post(
      ApiEndpoints.initiatePayment,
      data: {'charge_ids': chargeIds},
    );
    return response.data as Map<String, dynamic>;
  }
}
