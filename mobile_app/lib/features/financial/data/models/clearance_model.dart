import 'package:equatable/equatable.dart';

// DRF's DecimalField serializes as a JSON string — see ChargeModel's
// identical note. Parse via toString() so it works whether the value
// arrives as a JSON string or a JSON number.
double _parseAmount(dynamic value) {
  if (value == null) return 0;
  return double.parse(value.toString());
}

class ClearanceStatementModel extends Equatable {
  final int id;
  final int unit;
  final String unitKey;
  final DateTime? periodStart;
  final DateTime asOfDate;
  final double totalDue;
  final double totalPaid;
  final double totalRemaining;
  final bool isClear;
  final String? pdfUrl;
  final DateTime createdAt;

  const ClearanceStatementModel({
    required this.id,
    required this.unit,
    required this.unitKey,
    this.periodStart,
    required this.asOfDate,
    required this.totalDue,
    required this.totalPaid,
    required this.totalRemaining,
    required this.isClear,
    this.pdfUrl,
    required this.createdAt,
  });

  factory ClearanceStatementModel.fromJson(Map<String, dynamic> json) {
    return ClearanceStatementModel(
      id: json['id'] as int,
      unit: json['unit'] as int,
      unitKey: json['unit_key'] as String? ?? '',
      periodStart: json['period_start'] != null ? DateTime.parse(json['period_start'] as String) : null,
      asOfDate: DateTime.parse(json['as_of_date'] as String),
      totalDue: _parseAmount(json['total_due']),
      totalPaid: _parseAmount(json['total_paid']),
      totalRemaining: _parseAmount(json['total_remaining']),
      isClear: json['is_clear'] as bool? ?? false,
      pdfUrl: json['pdf_url'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  @override
  List<Object?> get props => [id, unit, unitKey, periodStart, asOfDate, totalDue, totalPaid, totalRemaining, isClear, pdfUrl, createdAt];
}
