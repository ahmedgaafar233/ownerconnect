import 'package:equatable/equatable.dart';

class ChargeDeferral extends Equatable {
  final String deferredTo;
  final String status;

  const ChargeDeferral({required this.deferredTo, required this.status});

  factory ChargeDeferral.fromJson(Map<String, dynamic> json) {
    return ChargeDeferral(
      deferredTo: json['deferred_to'] as String? ?? '',
      status: json['status'] as String? ?? '',
    );
  }

  @override
  List<Object?> get props => [deferredTo, status];
}

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
  final ChargeDeferral? activeDeferral;

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
    this.activeDeferral,
  });

  // DRF's DecimalField serializes as a JSON string (e.g. "30.00"), not a
  // number, to avoid float precision loss — confirmed on a real device
  // (`json['amount'] as num` threw "type 'String' is not a subtype of type
  // 'num'" as soon as a charge had a non-zero amount). Parse via
  // num.parse(toString()) so it works whether the value ever arrives as a
  // JSON string or a JSON number.
  static double _parseAmount(dynamic value) {
    if (value == null) return 0;
    return double.parse(value.toString());
  }

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
      amount: _parseAmount(json['amount']),
      paidAmount: _parseAmount(json['paid_amount']),
      remainingBalance: _parseAmount(json['remaining_balance']),
      isPaid: json['is_paid'] as bool? ?? false,
      notes: json['notes'] as String? ?? '',
      status: json['status'] as String? ?? '',
      createdAt: json['created_at'] as String? ?? '',
      activeDeferral: json['active_deferral'] != null
          ? ChargeDeferral.fromJson(json['active_deferral'] as Map<String, dynamic>)
          : null,
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
        activeDeferral,
      ];
}
