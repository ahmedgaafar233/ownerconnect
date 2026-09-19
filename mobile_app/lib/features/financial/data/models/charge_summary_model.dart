import 'package:equatable/equatable.dart';

// DRF's DecimalField serializes as a JSON string — see ChargeModel's
// identical note. Parse via toString() so it works whether the value
// arrives as a JSON string or a JSON number.
double _parseAmount(dynamic value) {
  if (value == null) return 0;
  return double.parse(value.toString());
}

class UnitBalanceModel extends Equatable {
  final int unit;
  final String unitKey;
  final double remaining;

  const UnitBalanceModel({
    required this.unit,
    required this.unitKey,
    required this.remaining,
  });

  factory UnitBalanceModel.fromJson(Map<String, dynamic> json) {
    return UnitBalanceModel(
      unit: json['unit'] as int,
      unitKey: json['unit_key'] as String? ?? '',
      remaining: _parseAmount(json['remaining']),
    );
  }

  @override
  List<Object?> get props => [unit, unitKey, remaining];
}

class ChargeSummaryModel extends Equatable {
  final double totalDue;
  final double totalPaid;
  final double totalRemaining;
  final List<UnitBalanceModel> byUnit;

  const ChargeSummaryModel({
    required this.totalDue,
    required this.totalPaid,
    required this.totalRemaining,
    required this.byUnit,
  });

  factory ChargeSummaryModel.fromJson(Map<String, dynamic> json) {
    return ChargeSummaryModel(
      totalDue: _parseAmount(json['total_due']),
      totalPaid: _parseAmount(json['total_paid']),
      totalRemaining: _parseAmount(json['total_remaining']),
      byUnit: (json['by_unit'] as List? ?? [])
          .map((e) => UnitBalanceModel.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  @override
  List<Object?> get props => [totalDue, totalPaid, totalRemaining, byUnit];
}
