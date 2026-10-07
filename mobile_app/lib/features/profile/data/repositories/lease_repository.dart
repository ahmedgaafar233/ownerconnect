import 'package:dio/dio.dart';

import '../../../../core/constants/api_endpoints.dart';
import '../models/lease_inputs.dart';
import '../models/lease_model.dart';

class LeaseRepository {
  final Dio dio;

  LeaseRepository({required this.dio});

  /// Registers a rental. The ID photo goes up as a file (multipart) — the
  /// server keeps it private; only the village's front desk can open it.
  Future<LeaseModel> createLease({
    required int unitId,
    required String term,
    required String startDate,
    required String endDate,
    required String tenantName,
    required String tenantPhone,
    required String tenantNationalId,
    required String idPhotoPath,
    required int occupants,
  }) async {
    final form = FormData.fromMap({
      'unit': unitId,
      'term': term,
      'start_date': startDate,
      'end_date': endDate,
      'tenant_name': tenantName,
      'tenant_phone': tenantPhone,
      'tenant_national_id': tenantNationalId,
      'occupants': occupants,
      'tenant_id_photo': await MultipartFile.fromFile(idPhotoPath, filename: _fileName(idPhotoPath)),
    });
    final response = await dio.post(ApiEndpoints.leases, data: form);
    return LeaseModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<LeaseModel> addAdult(int leaseId, AdultInput adult) async {
    final form = FormData.fromMap({
      'full_name': adult.fullName,
      'national_id': adult.nationalId,
      'relation': adult.relation,
      'id_photo': await MultipartFile.fromFile(adult.photoPath, filename: _fileName(adult.photoPath)),
    });
    final response = await dio.post(ApiEndpoints.leaseAdults(leaseId), data: form);
    return LeaseModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<LeaseModel> removeAdult(int leaseId, int adultId) async {
    final response = await dio.delete(ApiEndpoints.leaseAdult(leaseId, adultId));
    return LeaseModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<LeaseModel> addDocument(int leaseId, DocumentInput document) async {
    final form = FormData.fromMap({
      'kind': document.kind,
      'label': document.label,
      'file': await MultipartFile.fromFile(document.photoPath, filename: _fileName(document.photoPath)),
    });
    final response = await dio.post(ApiEndpoints.leaseDocuments(leaseId), data: form);
    return LeaseModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<LeaseModel> removeDocument(int leaseId, int documentId) async {
    final response = await dio.delete(ApiEndpoints.leaseDocument(leaseId, documentId));
    return LeaseModel.fromJson(response.data as Map<String, dynamic>);
  }

  /// Moves the end of a running rental later; the same QRs keep working.
  Future<LeaseModel> extendLease(int leaseId, String endDate) async {
    final response = await dio.post(ApiEndpoints.leaseExtend(leaseId), data: {'end_date': endDate});
    return LeaseModel.fromJson(response.data as Map<String, dynamic>);
  }

  /// A new period for the same tenant, people and QRs.
  Future<LeaseModel> renewLease(int leaseId, {required String startDate, required String endDate, String? term}) async {
    final response = await dio.post(
      ApiEndpoints.leaseRenew(leaseId),
      data: {'start_date': startDate, 'end_date': endDate, if (term != null) 'term': term},
    );
    return LeaseModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<LeaseModel> endLease(int leaseId) async {
    final response = await dio.post(ApiEndpoints.leaseEnd(leaseId));
    return LeaseModel.fromJson(response.data as Map<String, dynamic>);
  }

  static String _fileName(String path) {
    final name = path.split(RegExp(r'[\\/]')).last;
    return name.isEmpty ? 'id-photo.jpg' : name;
  }
}
