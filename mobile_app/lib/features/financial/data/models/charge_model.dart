import 'package:equatable/equatable.dart';

class ChargeModel extends Equatable {
  final int id;
  final int unit;
  final String unitKey;
  final int resort;
  final String resortName;
  final int year;
  final int? month;
  final String type;
  final double amount;
  final double paidAmount;
  final double remainingBalance;
  final bool isPaid;
  final String notes;
  final String status;
  final String createdAt;

  const ChargeModel({
    required this.id,
    required this.unit,
    required this.unitKey,
    required this.resort,
    required this.resortName,
    required this.year,
    this.month,
    required this.type,
    required this.amount,
    required this.paidAmount,
    required this.remainingBalance,
    required this.isPaid,
    required this.notes,
    required this.status,
    required this.createdAt,
  });

  factory ChargeModel.fromJson(Map<String, dynamic> json) {
    return ChargeModel(
      id: json['id'] as int,
      unit: json['unit'] as int,
      unitKey: json['unit_key'] as String? ?? '',
      resort: json['resort'] as int,
      resortName: json['resort_name'] as String? ?? '',
      year: json['year'] as int,
      month: json['month'] as int?,
      type: json['type'] as String? ?? '',
      amount: (json['amount'] as num).toDouble(),
      paidAmount: (json['paid_amount'] as num? ?? 0).toDouble(),
      remainingBalance: (json['remaining_balance'] as num? ?? 0).toDouble(),
      isPaid: json['is_paid'] as bool? ?? false,
      notes: json['notes'] as String? ?? '',
      status: json['status'] as String? ?? '',
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
        year,
        month,
        type,
        amount,
        paidAmount,
        remainingBalance,
        isPaid,
        notes,
        status,
        createdAt,
      ];
}
