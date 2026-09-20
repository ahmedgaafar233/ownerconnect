import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/utils/media_url.dart';
import '../../data/repositories/auth_repository.dart';
import 'auth_event.dart';
import 'auth_state.dart';

class AuthBloc extends Bloc<AuthEvent, AuthState> {
  final AuthRepository repository;

  AuthBloc({required this.repository}) : super(AuthInitialState()) {
    on<AuthCheckRequested>(_onAuthCheckRequested);
    on<PhoneSubmitted>(_onPhoneSubmitted);
    on<OtpSubmitted>(_onOtpSubmitted);
    on<DevBypassRequested>(_onDevBypassRequested);
    on<LogoutRequested>(_onLogoutRequested);
    on<PhoneCodeSent>(_onPhoneCodeSent);
    on<PhoneAutoVerified>(_onPhoneAutoVerified);
    on<PhoneVerificationFailed>(_onPhoneVerificationFailed);
    on<GoogleSignInRequested>(_onGoogleSignInRequested);
    on<EmailSignInRequested>(_onEmailSignInRequested);
    on<EmailRegisterRequested>(_onEmailRegisterRequested);
    on<AccountLinkSubmitted>(_onAccountLinkSubmitted);
  }

  Future<void> _onAuthCheckRequested(
    AuthCheckRequested event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoadingState());
    final loggedIn = await repository.isLoggedIn();
    if (!loggedIn) {
      emit(UnauthenticatedState());
      return;
    }
    await _resolveProfile(emit);
  }

  Future<void> _onPhoneSubmitted(
    PhoneSubmitted event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoadingState());
    try {
      await repository.verifyPhoneNumber(
        phoneNumber: event.phone,
        onCodeSent: (verificationId, resendToken) {
          add(PhoneCodeSent(verificationId: verificationId, phone: event.phone));
        },
        onVerificationCompleted: (credential) {
          add(PhoneAutoVerified(credential: credential));
        },
        onVerificationFailed: (error) {
          add(PhoneVerificationFailed(message: error.message ?? error.code));
        },
        onCodeAutoRetrievalTimeout: (_) {},
      );
    } catch (e) {
      emit(AuthErrorState(errorMessage: e.toString()));
    }
  }

  Future<void> _onOtpSubmitted(
    OtpSubmitted event,
    Emitter<AuthState> emit,
  ) async {
    final currentState = state;
    if (currentState is! OtpSentState) return;

    emit(AuthLoadingState());
    try {
      await repository.signInWithSmsCode(
        verificationId: currentState.verificationId,
        smsCode: event.smsCode,
      );
      await _resolveProfile(emit);
    } catch (e) {
      emit(AuthErrorState(errorMessage: e.toString()));
    }
  }

  Future<void> _onDevBypassRequested(
    DevBypassRequested event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoadingState());
    try {
      await repository.signInWithDevBypass(event.phone);
      await _resolveProfile(emit);
    } catch (e) {
      emit(AuthErrorState(errorMessage: e.toString()));
    }
  }

  Future<void> _onGoogleSignInRequested(
    GoogleSignInRequested event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoadingState());
    try {
      final result = await repository.signInWithGoogle();
      await _handleAuthResult(result, emit);
    } catch (e) {
      emit(AuthErrorState(errorMessage: e.toString()));
    }
  }

  Future<void> _onEmailSignInRequested(
    EmailSignInRequested event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoadingState());
    try {
      final result = await repository.signInWithEmail(email: event.email, password: event.password);
      await _handleAuthResult(result, emit);
    } catch (e) {
      emit(AuthErrorState(errorMessage: e.toString()));
    }
  }

  Future<void> _onEmailRegisterRequested(
    EmailRegisterRequested event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoadingState());
    try {
      final result = await repository.registerWithEmail(email: event.email, password: event.password);
      await _handleAuthResult(result, emit);
    } catch (e) {
      emit(AuthErrorState(errorMessage: e.toString()));
    }
  }

  Future<void> _onAccountLinkSubmitted(
    AccountLinkSubmitted event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoadingState());
    try {
      final result = await repository.linkAccount(phone: event.phone, code: event.code);
      await _handleAuthResult(result, emit);
    } catch (e) {
      emit(AuthErrorState(errorMessage: e.toString()));
    }
  }

  /// Shared tail for every Google/Email sign-in path: either the backend
  /// says this identity still needs linking, or it's authenticated and the
  /// normal profile/resort resolution proceeds.
  Future<void> _handleAuthResult(Map<String, dynamic> result, Emitter<AuthState> emit) async {
    if (result['link_required'] == true) {
      emit(AccountLinkRequiredState());
      return;
    }
    await _resolveProfile(emit);
  }

  Future<void> _onLogoutRequested(
    LogoutRequested event,
    Emitter<AuthState> emit,
  ) async {
    await repository.signOut();
    emit(UnauthenticatedState());
  }

  Future<void> _onPhoneCodeSent(
    PhoneCodeSent event,
    Emitter<AuthState> emit,
  ) async {
    emit(OtpSentState(verificationId: event.verificationId, phone: event.phone));
  }

  Future<void> _onPhoneAutoVerified(
    PhoneAutoVerified event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthLoadingState());
    try {
      await repository.signInWithCredential(event.credential);
      await _resolveProfile(emit);
    } catch (e) {
      emit(AuthErrorState(errorMessage: e.toString()));
    }
  }

  Future<void> _onPhoneVerificationFailed(
    PhoneVerificationFailed event,
    Emitter<AuthState> emit,
  ) async {
    emit(AuthErrorState(errorMessage: event.message));
  }

  /// Shared tail of every successful sign-in path (real OTP, auto-verification,
  /// dev bypass) and of the startup session check: resolve /api/me/, persist
  /// the resort, and emit the state that reflects whether one is linked yet.
  Future<void> _resolveProfile(Emitter<AuthState> emit) async {
    try {
      final profile = await repository.fetchAndPersistProfile();
      final resortId = profile['resort'];
      final resortName = profile['resort_name'] as String?;
      final resortLogoUrl = resolveMediaUrl(profile['resort_logo_url'] as String?);

      if (resortId == null) {
        emit(AwaitingResortAssignmentState(userId: profile['id'] as int));
      } else {
        emit(AuthenticatedState(
          userId: profile['id'] as int,
          role: profile['role'] as String,
          resortId: resortId as int,
          resortName: resortName ?? '',
          resortLogoUrl: resortLogoUrl,
        ));
      }
    } catch (e) {
      emit(UnauthenticatedState());
    }
  }
}
