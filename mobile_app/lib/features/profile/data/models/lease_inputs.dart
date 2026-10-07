import 'package:equatable/equatable.dart';

/// An adult entered on the rent-out form (or added later): who they are, how
/// they relate to the tenant, and a photo of their ID or passport.
class AdultInput extends Equatable {
  final String fullName;
  final String nationalId;
  final String relation; // SPOUSE | FAMILY | OTHER
  final String photoPath;

  const AdultInput({
    required this.fullName,
    required this.nationalId,
    required this.relation,
    required this.photoPath,
  });

  @override
  List<Object?> get props => [fullName, nationalId, relation, photoPath];
}

/// A paper sent with the rental: marriage certificate, passport, other.
class DocumentInput extends Equatable {
  final String kind; // MARRIAGE_CERT | PASSPORT | OTHER
  final String label;
  final String photoPath;

  const DocumentInput({required this.kind, this.label = '', required this.photoPath});

  @override
  List<Object?> get props => [kind, label, photoPath];
}
