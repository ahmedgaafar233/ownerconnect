import 'package:equatable/equatable.dart';

import 'lease_model.dart';

/// One unit from `/api/me/` — what the signed-in person has there.
class ProfileUnit extends Equatable {
  final int id;
  final String unitKey;
  final String buildingNo;
  final String unitNo;
  final String? unitTypeName;
  final int? cardAllowance;
  final int cardsUsed;

  /// OWNER or TENANT — how this person relates to *this* unit.
  final String relation;

  /// The rental running (or next coming up) on it, if any.
  final LeaseModel? lease;

  const ProfileUnit({
    required this.id,
    required this.unitKey,
    this.buildingNo = '',
    this.unitNo = '',
    this.unitTypeName,
    this.cardAllowance,
    this.cardsUsed = 0,
    this.relation = 'OWNER',
    this.lease,
  });

  factory ProfileUnit.fromJson(Map<String, dynamic> json) {
    final lease = json['lease'];
    return ProfileUnit(
      id: json['id'] as int,
      unitKey: json['unit_key'] as String? ?? '',
      buildingNo: json['building_no'] as String? ?? '',
      unitNo: json['unit_no'] as String? ?? '',
      unitTypeName: json['unit_type_name'] as String?,
      cardAllowance: json['card_allowance'] as int?,
      cardsUsed: json['cards_used'] as int? ?? 0,
      relation: json['relation'] as String? ?? 'OWNER',
      lease: lease is Map<String, dynamic> ? LeaseModel.fromJson(lease) : null,
    );
  }

  static List<ProfileUnit> listFrom(Object? raw) => (raw as List? ?? const [])
      .whereType<Map<String, dynamic>>()
      .map(ProfileUnit.fromJson)
      .toList();

  bool get isOwnerUnit => relation == 'OWNER';

  @override
  List<Object?> get props => [id, unitKey, buildingNo, unitNo, unitTypeName, cardAllowance, cardsUsed, relation, lease];
}
