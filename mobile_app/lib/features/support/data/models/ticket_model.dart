import 'package:equatable/equatable.dart';

class TicketModel extends Equatable {
  final int id;
  final String mobileTicketId;
  final int unit;
  final String unitKey;
  final String resortName;
  final String category;
  final String priority;
  final String subject;
  final String description;
  final String status;
  final bool isOverdue;
  final String createdAt;

  const TicketModel({
    required this.id,
    required this.mobileTicketId,
    required this.unit,
    required this.unitKey,
    required this.resortName,
    required this.category,
    required this.priority,
    required this.subject,
    required this.description,
    required this.status,
    required this.isOverdue,
    required this.createdAt,
  });

  factory TicketModel.fromJson(Map<String, dynamic> json) {
    return TicketModel(
      id: json['id'] as int,
      mobileTicketId: json['mobile_ticket_id'] as String? ?? '',
      unit: json['unit'] as int,
      unitKey: json['unit_key'] as String? ?? '',
      resortName: json['resort_name'] as String? ?? '',
      category: json['category'] as String? ?? '',
      priority: json['priority'] as String? ?? '',
      subject: json['subject'] as String? ?? '',
      description: json['description'] as String? ?? '',
      status: json['status'] as String? ?? '',
      isOverdue: json['is_overdue'] as bool? ?? false,
      createdAt: json['created_at'] as String? ?? '',
    );
  }

  @override
  List<Object?> get props => [
        id,
        mobileTicketId,
        unit,
        unitKey,
        resortName,
        category,
        priority,
        subject,
        description,
        status,
        isOverdue,
        createdAt,
      ];
}
