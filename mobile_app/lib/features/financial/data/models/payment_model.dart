import 'package:equatable/equatable.dart';

// DRF's DecimalField serializes as a JSON string (e.g. "30.00"), not a
// number — see ChargeModel's identical note. Parse via toString() so it
// works whether the value arrives as a JSON string or a JSON number.
double _parseAmount(dynamic value) {
  if (value == null) return 0;
  return double.parse(value.toString());
}

class PaymentAllocationModel extends Equatable {
  final int id;
  final int charge;
  final String chargeType;
  final int? chargeYear;
  final int? chargeMonth;
  final double amount;

  const PaymentAllocationModel({
    required this.id,
    required this.charge,
    required this.chargeType,
    this.chargeYear,
    this.chargeMonth,
    required this.amount,
  });

  factory PaymentAllocationModel.fromJson(Map<String, dynamic> json) {
    return PaymentAllocationModel(
      id: json['id'] as int,
      charge: json['charge'] as int,
      chargeType: json['charge_type'] as String? ?? '',
      chargeYear: json['charge_year'] as int?,
      chargeMonth: json['charge_month'] as int?,
      amount: _parseAmount(json['amount']),
    );
  }

  @override
  List<Object?> get props => [id, charge, chargeType, chargeYear, chargeMonth, amount];
}

class PaymentModel extends Equatable {
  final int id;
  final int unit;
  final String unitKey;
  final int resort;
  final String resortName;
  final String receiptNo;
  final String? receiptPdfUrl;
  final double totalAmount;
  final String paidAt;
  final String notes;
  final List<PaymentAllocationModel> allocations;
  final String createdAt;

  const PaymentModel({
    required this.id,
    required this.unit,
    required this.unitKey,
    required this.resort,
    required this.resortName,
    required this.receiptNo,
    this.receiptPdfUrl,
    required this.totalAmount,
    required this.paidAt,
    required this.notes,
    required this.allocations,
    required this.createdAt,
  });

  factory PaymentModel.fromJson(Map<String, dynamic> json) {
    return PaymentModel(
      id: json['id'] as int,
      unit: json['unit'] as int,
      unitKey: json['unit_key'] as String? ?? '',
      resort: json['resort'] as int,
      resortName: json['resort_name'] as String? ?? '',
      receiptNo: json['receipt_no'] as String? ?? '',
      receiptPdfUrl: json['receipt_pdf_url'] as String?,
      totalAmount: _parseAmount(json['total_amount']),
      paidAt: json['paid_at'] as String? ?? '',
      notes: json['notes'] as String? ?? '',
      allocations: (json['allocations'] as List? ?? [])
          .map((e) => PaymentAllocationModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      createdAt: json['created_at'] as String? ?? '',
    );
  }

  @override
  List<Object?> get props => [
        id,
        unit,
        unitKey,
        resort,
        resortName,
        receiptNo,
        receiptPdfUrl,
        totalAmount,
        paidAt,
        notes,
        allocations,
        createdAt,
      ];
}
