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

  /// Self-service only — the backend rejects anything more than 3 days out
  /// (ChargeDeferView / PaymentDeferralSerializer.validate_deferred_to).
  Future<Map<String, dynamic>> deferCharge({required int chargeId, required String deferredTo}) async {
    final response = await dio.post(
      ApiEndpoints.chargeDefer(chargeId),
      data: {'deferred_to': deferredTo},
    );
    return response.data as Map<String, dynamic>;
  }

  /// installments: list of {'due_date': 'YYYY-MM-DD', 'amount': '250.00'}.
  Future<Map<String, dynamic>> createPaymentPlan({
    required int chargeId,
    required List<Map<String, String>> installments,
  }) async {
    final response = await dio.post(
      ApiEndpoints.paymentPlans,
      data: {'charge': chargeId, 'installments': installments},
    );
    return response.data as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> getPaymentPlans() async {
    final response = await dio.get(ApiEndpoints.paymentPlans);
    final results = response.data['results'] as List;
    return results.cast<Map<String, dynamic>>();
  }
}
