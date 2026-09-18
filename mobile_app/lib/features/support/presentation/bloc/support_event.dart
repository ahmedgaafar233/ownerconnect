import 'package:equatable/equatable.dart';

abstract class SupportEvent extends Equatable {
  const SupportEvent();

  @override
  List<Object?> get props => [];
}

class FetchTicketsEvent extends SupportEvent {
  final int page;
  final String? category;
  final String? status;

  const FetchTicketsEvent({this.page = 1, this.category, this.status});

  @override
  List<Object?> get props => [page, category, status];
}

class CreateTicketEvent extends SupportEvent {
  final int unitId;
  final String category;
  final String priority;
  final String subject;
  final String description;

  const CreateTicketEvent({
    required this.unitId,
    required this.category,
    required this.priority,
    required this.subject,
    required this.description,
  });

  @override
  List<Object?> get props => [unitId, category, priority, subject, description];
}

class FetchVisitorPassesEvent extends SupportEvent {
  final int page;

  const FetchVisitorPassesEvent({this.page = 1});

  @override
  List<Object?> get props => [page];
}

class CreateVisitorPassEvent extends SupportEvent {
  final int unitId;
  final String passType;
  final String visitorName;
  final String nationalId;
  final String carPlate;
  final String validFrom;
  final String validTo;

  const CreateVisitorPassEvent({
    required this.unitId,
    required this.passType,
    required this.visitorName,
    required this.nationalId,
    required this.carPlate,
    required this.validFrom,
    required this.validTo,
  });

  @override
  List<Object?> get props => [
        unitId,
        passType,
        visitorName,
        nationalId,
        carPlate,
        validFrom,
        validTo,
      ];
}
