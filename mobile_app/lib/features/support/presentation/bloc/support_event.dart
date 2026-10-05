import 'package:equatable/equatable.dart';

abstract class SupportEvent extends Equatable {
  const SupportEvent();

  @override
  List<Object?> get props => [];
}

class FetchTicketsEvent extends SupportEvent {
  final int page;
  final String? category;

  /// "I'll pay cash at the accounts office" notes are stored as ACCOUNTS
  /// tickets, but they belong to the payment flow — the Support & Maintenance
  /// list is for service requests, so it leaves them out by default.
  final String? excludeCategory;
  final String? status;

  const FetchTicketsEvent({this.page = 1, this.category, this.excludeCategory = 'ACCOUNTS', this.status});

  @override
  List<Object?> get props => [page, category, excludeCategory, status];
}

class CreateTicketEvent extends SupportEvent {
  final int unitId;
  final String category;
  // Stable code the backend routes on (the subject is localized free text).
  final String serviceType;
  final String priority;
  final String subject;
  final String description;

  const CreateTicketEvent({
    required this.unitId,
    required this.category,
    this.serviceType = '',
    required this.priority,
    required this.subject,
    required this.description,
  });

  @override
  List<Object?> get props => [unitId, category, serviceType, priority, subject, description];
}
