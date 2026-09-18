import 'package:dio/dio.dart';
import '../../../../core/constants/api_endpoints.dart';
import '../models/ticket_model.dart';
import '../models/visitor_pass_model.dart';

class SupportRepository {
  final Dio dio;

  SupportRepository({required this.dio});

  Future<List<TicketModel>> getTickets({int page = 1, String? category, String? status}) async {
    final queryParams = <String, dynamic>{'page': page};
    if (category != null && category.isNotEmpty) queryParams['category'] = category;
    if (status != null && status.isNotEmpty) queryParams['status'] = status;

    final response = await dio.get(ApiEndpoints.tickets, queryParameters: queryParams);
    final results = response.data['results'] as List;
    return results.map((e) => TicketModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<TicketModel> createTicket({
    required int unitId,
    required String category,
    required String priority,
    required String subject,
    required String description,
  }) async {
    final response = await dio.post(
      ApiEndpoints.tickets,
      data: {
        'unit': unitId,
        'category': category,
        'priority': priority,
        'subject': subject,
        'description': description,
      },
    );
    return TicketModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<VisitorPassModel>> getVisitorPasses({int page = 1}) async {
    final response = await dio.get(ApiEndpoints.passes, queryParameters: {'page': page});
    final results = response.data['results'] as List;
    return results.map((e) => VisitorPassModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<VisitorPassModel> createVisitorPass({
    required int unitId,
    required String passType,
    required String visitorName,
    required String nationalId,
    required String carPlate,
    required String validFrom,
    required String validTo,
  }) async {
    final response = await dio.post(
      ApiEndpoints.passes,
      data: {
        'unit': unitId,
        'pass_type': passType,
        'visitor_name': visitorName,
        'national_id_or_passport': nationalId,
        'car_plate': carPlate,
        'valid_from': validFrom,
        'valid_to': validTo,
      },
    );
    return VisitorPassModel.fromJson(response.data as Map<String, dynamic>);
  }
}
