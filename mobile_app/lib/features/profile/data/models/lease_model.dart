import 'package:equatable/equatable.dart';

import '../../../support/data/models/visitor_pass_model.dart';

/// One QR pass of a rental: what to draw, whether it works, and until when.
class LeasePass extends Equatable {
  final int id;
  final String passCode;
  final String status; // ACTIVE | CANCELLED | …
  final String validFrom;
  final String validTo;

  const LeasePass({
    required this.id,
    required this.passCode,
    required this.status,
    this.validFrom = '',
    this.validTo = '',
  });

  factory LeasePass.fromJson(Map<String, dynamic> json) => LeasePass(
        id: json['id'] as int,
        passCode: json['pass_code'] as String? ?? '',
        status: json['status'] as String? ?? '',
        validFrom: json['valid_from'] as String? ?? '',
        validTo: json['valid_to'] as String? ?? '',
      );

  bool get isActive => status == 'ACTIVE';

  /// The same pass in the shape the existing QR dialog draws.
  VisitorPassModel toVisitorPass({required int unitId, required String unitKey, required String name}) {
    return VisitorPassModel(
      id: id,
      passCode: passCode,
      unit: unitId,
      unitKey: unitKey,
      resortName: '',
      passType: 'TENANT',
      visitorName: name,
      nationalIdOrPassport: '',
      carPlate: '',
      validFrom: validFrom,
      validTo: validTo,
      status: status,
      createdAt: '',
    );
  }

  @override
  List<Object?> get props => [id, passCode, status, validFrom, validTo];
}

/// An adult staying in the rented unit besides the tenant.
class LeaseAdultModel extends Equatable {
  final int id;
  final String fullName;
  final String nationalId;
  final String relation; // SPOUSE | FAMILY | OTHER
  final LeasePass? access;

  const LeaseAdultModel({
    required this.id,
    required this.fullName,
    this.nationalId = '',
    this.relation = 'SPOUSE',
    this.access,
  });

  factory LeaseAdultModel.fromJson(Map<String, dynamic> json) {
    final access = json['access'];
    return LeaseAdultModel(
      id: json['id'] as int,
      fullName: json['full_name'] as String? ?? '',
      nationalId: json['national_id'] as String? ?? '',
      relation: json['relation'] as String? ?? 'SPOUSE',
      access: access is Map<String, dynamic> ? LeasePass.fromJson(access) : null,
    );
  }

  @override
  List<Object?> get props => [id, fullName, nationalId, relation, access];
}

class LeaseDocumentModel extends Equatable {
  final int id;
  final String kind; // MARRIAGE_CERT | PASSPORT | OTHER
  final String label;

  const LeaseDocumentModel({required this.id, required this.kind, this.label = ''});

  factory LeaseDocumentModel.fromJson(Map<String, dynamic> json) => LeaseDocumentModel(
        id: json['id'] as int,
        kind: json['kind'] as String? ?? 'OTHER',
        label: json['label'] as String? ?? '',
      );

  @override
  List<Object?> get props => [id, kind, label];
}

/// One meter reading as Maintenance recorded it.
class MeterReadingValue extends Equatable {
  final String reading; // e.g. "1500.50"
  final String readOn; // yyyy-MM-dd

  const MeterReadingValue({required this.reading, required this.readOn});

  factory MeterReadingValue.fromJson(Map<String, dynamic> json) => MeterReadingValue(
        reading: json['reading'] as String? ?? '',
        readOn: json['read_on'] as String? ?? '',
      );

  @override
  List<Object?> get props => [reading, readOn];
}

/// The entry and exit readings of one meter (either may not be taken yet).
class MeterPair extends Equatable {
  final MeterReadingValue? entry;
  final MeterReadingValue? exit;

  const MeterPair({this.entry, this.exit});

  factory MeterPair.fromJson(Map<String, dynamic> json) => MeterPair(
        entry: json['entry'] is Map<String, dynamic> ? MeterReadingValue.fromJson(json['entry']) : null,
        exit: json['exit'] is Map<String, dynamic> ? MeterReadingValue.fromJson(json['exit']) : null,
      );

  @override
  List<Object?> get props => [entry, exit];
}

/// Parses `{"ELECTRICITY": {entry, exit}, "WATER": {entry, exit}}`.
Map<String, MeterPair> parseMeterReadings(Object? raw) {
  if (raw is! Map) return const {};
  return {
    for (final entry in raw.entries)
      if (entry.value is Map<String, dynamic>) entry.key as String: MeterPair.fromJson(entry.value as Map<String, dynamic>),
  };
}

/// A rental of one unit. The owner's copy carries the tenant's details; the
/// tenant's own copy (inside `/api/me/`) only has the period, so everything
/// about the tenant is optional.
class LeaseModel extends Equatable {
  final int? id;
  final int unitId;
  final String term; // SHORT | LONG | '' (tenant's own copy doesn't say)
  final String status; // UPCOMING | ACTIVE | ENDED | CANCELLED
  final String startDate; // yyyy-MM-dd
  final String endDate;
  final String tenantName;
  final String tenantPhone;
  final String tenantNationalId;
  final int occupants;

  /// What the tenant still owes on their own months — only for a long lease.
  final String? tenantBalance;
  final bool? tenantCleared;

  /// The tenant's own QR, then each further adult's.
  final LeasePass? access;
  final List<LeaseAdultModel> adults;
  final List<LeaseDocumentModel> documents;

  /// Adults the unit has room for, the tenant included.
  final int maxAdults;

  /// The meters Maintenance read at entry and exit — ELECTRICITY and WATER.
  final Map<String, MeterPair> meterReadings;

  const LeaseModel({
    this.id,
    this.unitId = 0,
    this.term = '',
    required this.status,
    required this.startDate,
    required this.endDate,
    this.tenantName = '',
    this.tenantPhone = '',
    this.tenantNationalId = '',
    this.occupants = 0,
    this.tenantBalance,
    this.tenantCleared,
    this.access,
    this.adults = const [],
    this.documents = const [],
    this.maxAdults = 10,
    this.meterReadings = const {},
  });

  factory LeaseModel.fromJson(Map<String, dynamic> json) {
    final access = json['access'];
    return LeaseModel(
      id: json['id'] as int?,
      unitId: json['unit'] as int? ?? 0,
      term: json['term'] as String? ?? '',
      status: json['status'] as String? ?? 'ACTIVE',
      startDate: json['start_date'] as String? ?? '',
      endDate: json['end_date'] as String? ?? '',
      tenantName: json['tenant_name'] as String? ?? '',
      tenantPhone: json['tenant_phone'] as String? ?? '',
      tenantNationalId: json['tenant_national_id'] as String? ?? '',
      occupants: json['occupants'] as int? ?? 0,
      tenantBalance: json['tenant_balance'] as String?,
      tenantCleared: json['tenant_cleared'] as bool?,
      access: access is Map<String, dynamic> ? LeasePass.fromJson(access) : null,
      adults: (json['adults'] as List? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(LeaseAdultModel.fromJson)
          .toList(),
      documents: (json['documents'] as List? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(LeaseDocumentModel.fromJson)
          .toList(),
      maxAdults: json['max_adults'] as int? ?? 10,
      meterReadings: parseMeterReadings(json['meter_readings']),
    );
  }

  bool get isLong => term == 'LONG';
  bool get isEnded => status == 'ENDED' || status == 'CANCELLED';

  /// A rental that hasn't finished can still be ended or extended by the owner.
  bool get canEnd => status == 'ACTIVE' || status == 'UPCOMING';

  /// Whether another adult fits: the tenant plus the adults already added.
  bool get canAddAdult => canEnd && 1 + adults.length < maxAdults;

  @override
  List<Object?> get props => [
        id,
        unitId,
        term,
        status,
        startDate,
        endDate,
        tenantName,
        tenantPhone,
        tenantNationalId,
        occupants,
        tenantBalance,
        tenantCleared,
        access,
        adults,
        documents,
        maxAdults,
        meterReadings,
      ];
}
