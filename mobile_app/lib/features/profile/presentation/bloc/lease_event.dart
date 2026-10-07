import 'package:equatable/equatable.dart';

import '../../data/models/lease_inputs.dart';

abstract class LeaseEvent extends Equatable {
  const LeaseEvent();

  @override
  List<Object?> get props => [];
}

class LeaseSubmitted extends LeaseEvent {
  final int unitId;
  final String term; // SHORT | LONG

  /// Calendar dates (yyyy-MM-dd), read by the server as the resort's own days.
  final String startDate;
  final String endDate;
  final String tenantName;

  /// E.164, e.g. +201005550001 — the number the tenant signs in with.
  final String tenantPhone;
  final String tenantNationalId;
  final String idPhotoPath;
  final int occupants;

  /// The other adults staying (each gets their own QR) and the papers going to
  /// the village. They're uploaded one by one right after the rental is created.
  final List<AdultInput> adults;
  final List<DocumentInput> documents;

  const LeaseSubmitted({
    required this.unitId,
    required this.term,
    required this.startDate,
    required this.endDate,
    required this.tenantName,
    required this.tenantPhone,
    required this.tenantNationalId,
    required this.idPhotoPath,
    required this.occupants,
    this.adults = const [],
    this.documents = const [],
  });

  @override
  List<Object?> get props => [
        unitId,
        term,
        startDate,
        endDate,
        tenantName,
        tenantPhone,
        tenantNationalId,
        idPhotoPath,
        occupants,
        adults,
        documents,
      ];
}

class LeaseEndRequested extends LeaseEvent {
  final int leaseId;

  const LeaseEndRequested(this.leaseId);

  @override
  List<Object?> get props => [leaseId];
}

class LeaseAdultAdded extends LeaseEvent {
  final int leaseId;
  final AdultInput adult;

  const LeaseAdultAdded(this.leaseId, this.adult);

  @override
  List<Object?> get props => [leaseId, adult];
}

class LeaseAdultRemoved extends LeaseEvent {
  final int leaseId;
  final int adultId;

  const LeaseAdultRemoved(this.leaseId, this.adultId);

  @override
  List<Object?> get props => [leaseId, adultId];
}

class LeaseDocumentAdded extends LeaseEvent {
  final int leaseId;
  final DocumentInput document;

  const LeaseDocumentAdded(this.leaseId, this.document);

  @override
  List<Object?> get props => [leaseId, document];
}

class LeaseDocumentRemoved extends LeaseEvent {
  final int leaseId;
  final int documentId;

  const LeaseDocumentRemoved(this.leaseId, this.documentId);

  @override
  List<Object?> get props => [leaseId, documentId];
}

/// Pushes a running rental's end date later; its QRs keep working.
class LeaseExtended extends LeaseEvent {
  final int leaseId;

  /// yyyy-MM-dd
  final String endDate;

  const LeaseExtended(this.leaseId, this.endDate);

  @override
  List<Object?> get props => [leaseId, endDate];
}

/// A new period for the same tenant: same people, papers and QRs.
class LeaseRenewed extends LeaseEvent {
  final int leaseId;
  final String startDate;
  final String endDate;

  /// SHORT | LONG — null keeps the current kind.
  final String? term;

  const LeaseRenewed(this.leaseId, {required this.startDate, required this.endDate, this.term});

  @override
  List<Object?> get props => [leaseId, startDate, endDate, term];
}
