import 'package:dio/dio.dart';

import 'package:owner_connect/features/auth/data/repositories/auth_repository.dart';
import 'package:owner_connect/features/support/data/models/ticket_model.dart';
import 'package:owner_connect/features/support/data/models/visitor_pass_model.dart';
import 'package:owner_connect/features/support/data/repositories/support_repository.dart';

/// Only the profile call matters to the support forms; everything else is
/// untouched.
class FakeAuthRepository implements AuthRepository {
  FakeAuthRepository(this.profile);
  final Map<String, dynamic> profile;

  @override
  Future<Map<String, dynamic>> fetchAndPersistProfile() async => profile;

  @override
  Future<bool> isLoggedIn() async => false;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// Records what the forms submit instead of calling the API.
class FakeSupportRepository implements SupportRepository {
  final createdPasses = <Map<String, dynamic>>[];
  final createdTickets = <Map<String, dynamic>>[];

  @override
  Dio get dio => throw UnimplementedError();

  @override
  Future<VisitorPassModel> createVisitorPass({
    required int unitId,
    required String passType,
    required String visitorName,
    required String nationalId,
    required String carPlate,
    required String startDate,
    required String endDate,
  }) async {
    createdPasses.add({
      'unitId': unitId,
      'passType': passType,
      'visitorName': visitorName,
      'startDate': startDate,
      'endDate': endDate,
    });
    return VisitorPassModel.fromJson({
      'id': 1,
      'unit': unitId,
      'pass_type': passType,
      'visitor_name': visitorName,
      'status': createdPassStatus,
    });
  }

  /// What the server says the new pass's status is: PENDING in a resort
  /// where Security approves requests, ACTIVE where owners self-issue.
  String createdPassStatus = 'PENDING';

  /// Passes the list screen loads.
  List<VisitorPassModel> passes = [];

  /// Makes the next list fetch fail, once.
  bool failNextPassFetch = false;

  @override
  Future<List<VisitorPassModel>> getVisitorPasses({int page = 1}) async {
    if (failNextPassFetch) {
      failNextPassFetch = false;
      throw Exception('network down');
    }
    return passes;
  }

  @override
  Future<List<TicketModel>> getTickets({
    int page = 1,
    String? category,
    String? excludeCategory,
    String? status,
  }) async {
    requestedExcludeCategories.add(excludeCategory);
    return [];
  }

  /// The exclude_category each ticket-list fetch asked for.
  final requestedExcludeCategories = <String?>[];

  @override
  Future<TicketModel> createTicket({
    required int unitId,
    required String category,
    String serviceType = '',
    required String priority,
    required String subject,
    required String description,
  }) async {
    createdTickets.add({
      'unitId': unitId,
      'category': category,
      'serviceType': serviceType,
      'subject': subject,
    });
    return TicketModel.fromJson({
      'id': 1,
      'unit': unitId,
      'category': category,
      'subject': subject,
    });
  }
}
