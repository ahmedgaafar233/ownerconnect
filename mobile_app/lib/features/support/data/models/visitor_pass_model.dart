import 'package:equatable/equatable.dart';

class VisitorPassModel extends Equatable {
  final int id;
  final String passCode;
  final int unit;
  final String unitKey;
  final String resortName;
  final String passType;
  final String visitorName;
  final String nationalIdOrPassport;
  final String carPlate;
  final String validFrom;
  final String validTo;
  final String status;
  final String createdAt;

  const VisitorPassModel({
    required this.id,
    required this.passCode,
    required this.unit,
    required this.unitKey,
    required this.resortName,
    required this.passType,
    required this.visitorName,
    required this.nationalIdOrPassport,
    required this.carPlate,
    required this.validFrom,
    required this.validTo,
    required this.status,
    required this.createdAt,
  });

  factory VisitorPassModel.fromJson(Map<String, dynamic> json) {
    return VisitorPassModel(
      id: json['id'] as int,
      passCode: json['pass_code'] as String? ?? '',
      unit: json['unit'] as int,
      unitKey: json['unit_key'] as String? ?? '',
      resortName: json['resort_name'] as String? ?? '',
      passType: json['pass_type'] as String? ?? '',
      visitorName: json['visitor_name'] as String? ?? '',
      nationalIdOrPassport: json['national_id_or_passport'] as String? ?? '',
      carPlate: json['car_plate'] as String? ?? '',
      validFrom: json['valid_from'] as String? ?? '',
      validTo: json['valid_to'] as String? ?? '',
      status: json['status'] as String? ?? '',
      createdAt: json['created_at'] as String? ?? '',
    );
  }

  @override
  List<Object?> get props => [
        id,
        passCode,
        unit,
        unitKey,
        resortName,
        passType,
        visitorName,
        nationalIdOrPassport,
        carPlate,
        validFrom,
        validTo,
        status,
        createdAt,
      ];
}
