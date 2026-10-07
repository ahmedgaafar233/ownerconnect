import 'package:equatable/equatable.dart';
import 'package:firebase_auth/firebase_auth.dart' as fb;

abstract class AuthEvent extends Equatable {
  const AuthEvent();

  @override
  List<Object?> get props => [];
}

/// Dispatched once on app start (from the splash screen) to check whether a
/// stored session is still valid.
class AuthCheckRequested extends AuthEvent {
  const AuthCheckRequested();
}

/// Re-reads /api/me/ for an already signed-in person, so what the drawer
/// shows (name, units) follows changes made elsewhere in the app — saving a
/// new name, renting a unit out — without waiting for the next app start.
class ProfileRefreshRequested extends AuthEvent {
  const ProfileRefreshRequested();
}

class PhoneSubmitted extends AuthEvent {
  final String phone;

  const PhoneSubmitted({required this.phone});

  @override
  List<Object?> get props => [phone];
}

class OtpSubmitted extends AuthEvent {
  final String smsCode;

  const OtpSubmitted({required this.smsCode});

  @override
  List<Object?> get props => [smsCode];
}

class GoogleSignInRequested extends AuthEvent {
  const GoogleSignInRequested();
}

class EmailSignInRequested extends AuthEvent {
  final String email;
  final String password;

  const EmailSignInRequested({required this.email, required this.password});

  @override
  List<Object?> get props => [email, password];
}

class EmailRegisterRequested extends AuthEvent {
  final String email;
  final String password;

  const EmailRegisterRequested({required this.email, required this.password});

  @override
  List<Object?> get props => [email, password];
}

/// Submits phone + activation code to link a Google/Email sign-in that came
/// back as `link_required` to the owner staff already pre-provisioned.
class AccountLinkSubmitted extends AuthEvent {
  final String phone;
  final String code;

  const AccountLinkSubmitted({required this.phone, required this.code});

  @override
  List<Object?> get props => [phone, code];
}

/// Debug-only shortcut: skips real Firebase SMS and authenticates straight
/// against the backend's ALLOW_DEV_AUTH_BYPASS path. Never reachable outside
/// kDebugMode (gated in the UI, not just here).
class DevBypassRequested extends AuthEvent {
  final String phone;

  const DevBypassRequested({required this.phone});

  @override
  List<Object?> get props => [phone];
}

class LogoutRequested extends AuthEvent {
  const LogoutRequested();
}

// ── Internal events fed back into the bloc from FirebaseAuth's callback-based
//    verifyPhoneNumber API (it has no Future-based equivalent). ──────────────

class PhoneCodeSent extends AuthEvent {
  final String verificationId;
  final String phone;

  const PhoneCodeSent({required this.verificationId, required this.phone});

  @override
  List<Object?> get props => [verificationId, phone];
}

class PhoneAutoVerified extends AuthEvent {
  final fb.PhoneAuthCredential credential;

  const PhoneAutoVerified({required this.credential});

  @override
  List<Object?> get props => [credential];
}

class PhoneVerificationFailed extends AuthEvent {
  final String message;

  const PhoneVerificationFailed({required this.message});

  @override
  List<Object?> get props => [message];
}
