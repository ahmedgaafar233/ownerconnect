import 'package:dio/dio.dart';

import '../../../../core/constants/api_endpoints.dart';
import '../models/payment_method_model.dart';

class PaymentMethodRepository {
  final Dio dio;

  PaymentMethodRepository({required this.dio});

  Future<List<PaymentMethodModel>> list() async {
    final response = await dio.get(ApiEndpoints.paymentMethods);
    return (response.data as List)
        .whereType<Map<String, dynamic>>()
        .map(PaymentMethodModel.fromJson)
        .toList();
  }

  Future<PaymentMethodOptions> options() async {
    final response = await dio.get(ApiEndpoints.paymentMethodOptions);
    return PaymentMethodOptions.fromJson(response.data as Map<String, dynamic>);
  }

  Future<PaymentMethodModel> add({
    required String kind,
    String? walletProvider,
    String? walletPhone,
    String? instapayAddress,
    bool makeDefault = false,
  }) async {
    final response = await dio.post(ApiEndpoints.paymentMethods, data: {
      'kind': kind,
      if (walletProvider != null) 'wallet_provider': walletProvider,
      if (walletPhone != null) 'wallet_phone': walletPhone,
      if (instapayAddress != null) 'instapay_address': instapayAddress,
      'make_default': makeDefault,
    });
    return PaymentMethodModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<void> remove(int id) => dio.delete(ApiEndpoints.paymentMethod(id));

  Future<void> makeDefault(int id) => dio.post(ApiEndpoints.paymentMethodDefault(id));
}
