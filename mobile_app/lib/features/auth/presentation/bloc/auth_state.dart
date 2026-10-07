import 'package:equatable/equatable.dart';

import '../../../profile/data/models/profile_unit.dart';

abstract class AuthState extends Equatable {
  const AuthState();

  @override
  List<Object?> get props => [];
}

/// Nothing decided yet — splash screen is still checking stored credentials.
class AuthInitialState extends AuthState {}

class AuthLoadingState extends AuthState {}

/// No valid session — show the phone entry screen.
class UnauthenticatedState extends AuthState {}

class OtpSentState extends AuthState {
  final String verificationId;
  final String phone;

  const OtpSentState({required this.verificationId, required this.phone});

  @override
  List<Object?> get props => [verificationId, phone];
}

/// A Google/Email sign-in succeeded with Firebase but isn't linked to any
/// pre-provisioned owner yet — the app must collect phone + activation code.
class AccountLinkRequiredState extends AuthState {}

/// Signed in AND linked to a resort — the normal, fully-usable state.
class AuthenticatedState extends AuthState {
  final int userId;
  final String role;
  final int resortId;
  final String resortName;
  final String? resortLogoUrl;

  /// The owner's own name, for the drawer header — empty until they've set
  /// one; [phone] is what's shown instead.
  final String fullname;
  final String phone;

  /// The units this person has (as owner or tenant) — what identifies them in
  /// the app together with the village, shown under their name in the drawer.
  final List<ProfileUnit> units;

  const AuthenticatedState({
    required this.userId,
    required this.role,
    required this.resortId,
    required this.resortName,
    this.resortLogoUrl,
    this.fullname = '',
    this.phone = '',
    this.units = const [],
  });

  /// Who to call this person: their name, else their phone number.
  String get displayName => fullname.trim().isNotEmpty ? fullname.trim() : phone;

  @override
  List<Object?> get props => [userId, role, resortId, resortName, resortLogoUrl, fullname, phone, units];
}

/// Signed in but `resort` is still null on the backend — the account exists
/// but no admin has linked it to a village/unit yet.
class AwaitingResortAssignmentState extends AuthState {
  final int userId;

  const AwaitingResortAssignmentState({required this.userId});

  @override
  List<Object?> get props => [userId];
}

class AuthErrorState extends AuthState {
  final String errorMessage;

  const AuthErrorState({required this.errorMessage});

  @override
  List<Object?> get props => [errorMessage];
}
