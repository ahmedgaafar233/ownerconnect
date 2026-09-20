import 'package:equatable/equatable.dart';

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

  const AuthenticatedState({
    required this.userId,
    required this.role,
    required this.resortId,
    required this.resortName,
    this.resortLogoUrl,
  });

  @override
  List<Object?> get props => [userId, role, resortId, resortName, resortLogoUrl];
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
