import 'package:dio/dio.dart';

import 'package:owner_connect/features/auth/data/repositories/auth_repository.dart';
import 'package:owner_connect/features/profile/data/models/lease_inputs.dart';
import 'package:owner_connect/features/profile/data/models/lease_model.dart';
import 'package:owner_connect/features/profile/data/repositories/lease_repository.dart';

/// A signed-in owner whose profile can change (the name they save comes back
/// on the next read, as it does from the real server).
class ProfileFakeAuthRepository implements AuthRepository {
  ProfileFakeAuthRepository(this.profile);
  final Map<String, dynamic> profile;
  final savedNames = <String>[];

  @override
  Future<Map<String, dynamic>> fetchAndPersistProfile() async => Map<String, dynamic>.from(profile);

  @override
  Future<Map<String, dynamic>> updateFullname(String fullname) async {
    savedNames.add(fullname);
    profile['fullname'] = fullname;
    return Map<String, dynamic>.from(profile);
  }

  @override
  Future<bool> isLoggedIn() async => true;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// Records what the rent-out form submits instead of calling the API.
class FakeLeaseRepository implements LeaseRepository {
  final created = <Map<String, dynamic>>[];
  final ended = <int>[];

  /// When set, createLease fails with this server error body.
  Map<String, dynamic>? failWith;

  @override
  Dio get dio => throw UnimplementedError();

  @override
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
    final error = failWith;
    if (error != null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/api/owner/leases/'),
        response: Response(requestOptions: RequestOptions(path: '/api/owner/leases/'), statusCode: 400, data: error),
      );
    }
    created.add({
      'unitId': unitId,
      'term': term,
      'startDate': startDate,
      'endDate': endDate,
      'tenantName': tenantName,
      'tenantPhone': tenantPhone,
      'tenantNationalId': tenantNationalId,
      'idPhotoPath': idPhotoPath,
      'occupants': occupants,
    });
    return LeaseModel(id: 1, term: term, status: 'ACTIVE', startDate: startDate, endDate: endDate, tenantName: tenantName);
  }

  @override
  Future<LeaseModel> endLease(int leaseId) async {
    ended.add(leaseId);
    return LeaseModel(id: leaseId, status: 'ENDED', startDate: '2026-10-01', endDate: '2026-10-05');
  }

  // ── a rental that is already open: its people, papers, extension and renewal ──

  final addedAdults = <AdultInput>[];
  final removedAdults = <int>[];
  final addedDocuments = <DocumentInput>[];
  final removedDocuments = <int>[];
  final extended = <String>[];
  final renewed = <Map<String, String?>>[];

  /// What the server says the rental looks like after the next change.
  LeaseModel? next;

  LeaseModel _after(int leaseId, {String endDate = '2026-12-31'}) =>
      next ??
      LeaseModel(
        id: leaseId,
        term: 'LONG',
        status: 'ACTIVE',
        startDate: '2026-10-01',
        endDate: endDate,
        tenantName: 'Mona Tenant',
      );

  @override
  Future<LeaseModel> addAdult(int leaseId, AdultInput adult) async {
    addedAdults.add(adult);
    return _after(leaseId);
  }

  @override
  Future<LeaseModel> removeAdult(int leaseId, int adultId) async {
    removedAdults.add(adultId);
    return _after(leaseId);
  }

  @override
  Future<LeaseModel> addDocument(int leaseId, DocumentInput document) async {
    addedDocuments.add(document);
    return _after(leaseId);
  }

  @override
  Future<LeaseModel> removeDocument(int leaseId, int documentId) async {
    removedDocuments.add(documentId);
    return _after(leaseId);
  }

  @override
  Future<LeaseModel> extendLease(int leaseId, String endDate) async {
    extended.add(endDate);
    return _after(leaseId, endDate: endDate);
  }

  @override
  Future<LeaseModel> renewLease(int leaseId, {required String startDate, required String endDate, String? term}) async {
    renewed.add({'startDate': startDate, 'endDate': endDate, 'term': term});
    return _after(leaseId);
  }
}

Map<String, dynamic> ownerProfile({String fullname = 'Ahmed Gaafar', List<Map<String, dynamic>>? units}) => {
      'id': 16,
      'phone': '+201001234567',
      'fullname': fullname,
      'role': 'OWNER',
      'resort': 1,
      'resort_name': 'Delta Sharm',
      'resort_logo_url': null,
      'units': units ??
          [
            {
              'id': 88,
              'unit_key': 'DEMO-BELL-1',
              'building_no': '',
              'unit_no': '',
              'unit_type_name': 'Studio',
              'card_allowance': 2,
              'cards_used': 2,
              'relation': 'OWNER',
              'lease': null,
            },
            {
              'id': 89,
              'unit_key': 'DEMO-BELL-2',
              'building_no': 'B2',
              'unit_no': '12',
              'unit_type_name': null,
              'card_allowance': null,
              'cards_used': 0,
              'relation': 'OWNER',
              'lease': {
                'id': 5,
                'term': 'LONG',
                'status': 'ACTIVE',
                'start_date': '2026-10-01',
                'end_date': '2026-12-31',
                'tenant_name': 'Mona Tenant',
                'tenant_phone': '+201005550001',
                'tenant_national_id': '29001011234567',
                'occupants': 3,
                'tenant_balance': '200.00',
                'tenant_cleared': false,
              },
            },
          ],
    };
