import 'package:firebase_auth/firebase_auth.dart' as fb;
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_connect/core/router/app_router.dart';
import 'package:owner_connect/core/theme/app_theme.dart';
import 'package:owner_connect/features/auth/data/repositories/auth_repository.dart';
import 'package:owner_connect/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:owner_connect/features/auth/presentation/bloc/auth_event.dart';
import 'package:owner_connect/features/auth/presentation/bloc/auth_state.dart';
import 'package:owner_connect/features/auth/presentation/screens/phone_entry_screen.dart';

/// Never touches Firebase or secure storage — deterministic and instant,
/// unlike the real FirebaseAuthRepository which needs a configured Firebase
/// project and a real platform to run on.
class _FakeAuthRepository implements AuthRepository {
  bool loggedIn = false;

  @override
  Future<bool> isLoggedIn() async => loggedIn;

  @override
  Future<Map<String, dynamic>> fetchAndPersistProfile() async =>
      {'id': 1, 'role': 'OWNER', 'resort': 1, 'resort_name': 'Delta Sharm'};

  @override
  Future<Map<String, dynamic>> signInWithDevBypass(String phone) async => {};

  @override
  Future<Map<String, dynamic>> signInWithSmsCode({required String verificationId, required String smsCode}) async =>
      {};

  @override
  Future<Map<String, dynamic>> signInWithCredential(fb.PhoneAuthCredential credential) async => {};

  @override
  Future<void> verifyPhoneNumber({
    required String phoneNumber,
    required Function(String verificationId, int? resendToken) onCodeSent,
    required Function(fb.PhoneAuthCredential credential) onVerificationCompleted,
    required Function(fb.FirebaseAuthException error) onVerificationFailed,
    required Function(String verificationId) onCodeAutoRetrievalTimeout,
  }) async {}

  @override
  Future<void> signOut() async {}
}

void main() {
  testWidgets('with no stored session, the tenant gate routes to phone entry', (tester) async {
    final repository = _FakeAuthRepository()..loggedIn = false;
    final authBloc = AuthBloc(repository: repository);
    addTearDown(authBloc.close);

    await tester.pumpWidget(BlocProvider.value(
      value: authBloc,
      child: MaterialApp.router(
        theme: AppTheme.lightTheme,
        routerConfig: AppRouter.build(authBloc),
      ),
    ));
    await tester.pumpAndSettle();

    expect(find.byType(PhoneEntryScreen), findsOneWidget);
  });

  test('a valid stored session resolves Authenticated, locked to the right resort', () async {
    final repository = _FakeAuthRepository()..loggedIn = true;
    final authBloc = AuthBloc(repository: repository);
    addTearDown(authBloc.close);

    authBloc.add(const AuthCheckRequested());
    final state = await authBloc.stream.firstWhere((s) => s is AuthenticatedState) as AuthenticatedState;

    expect(state.resortId, 1);
    expect(state.resortName, 'Delta Sharm');
  });

  test('a session with no resort assigned yet resolves AwaitingResortAssignment', () async {
    final repository = _FakeAuthRepository()..loggedIn = true;
    final unassigned = _UnassignedFakeAuthRepository(repository);
    final authBloc = AuthBloc(repository: unassigned);
    addTearDown(authBloc.close);

    authBloc.add(const AuthCheckRequested());
    final state = await authBloc.stream.firstWhere((s) => s is AwaitingResortAssignmentState);

    expect(state, isA<AwaitingResortAssignmentState>());
  });
}

/// Wraps _FakeAuthRepository but returns a profile with no resort linked —
/// covers the "account exists, not yet assigned to a village" gap called out
/// in the product plan (see AwaitingResortAssignmentState).
class _UnassignedFakeAuthRepository implements AuthRepository {
  final _FakeAuthRepository _inner;
  _UnassignedFakeAuthRepository(this._inner);

  @override
  Future<bool> isLoggedIn() => _inner.isLoggedIn();

  @override
  Future<Map<String, dynamic>> fetchAndPersistProfile() async =>
      {'id': 2, 'role': 'OWNER', 'resort': null, 'resort_name': null};

  @override
  Future<Map<String, dynamic>> signInWithDevBypass(String phone) => _inner.signInWithDevBypass(phone);

  @override
  Future<Map<String, dynamic>> signInWithSmsCode({required String verificationId, required String smsCode}) =>
      _inner.signInWithSmsCode(verificationId: verificationId, smsCode: smsCode);

  @override
  Future<Map<String, dynamic>> signInWithCredential(fb.PhoneAuthCredential credential) =>
      _inner.signInWithCredential(credential);

  @override
  Future<void> verifyPhoneNumber({
    required String phoneNumber,
    required Function(String verificationId, int? resendToken) onCodeSent,
    required Function(fb.PhoneAuthCredential credential) onVerificationCompleted,
    required Function(fb.FirebaseAuthException error) onVerificationFailed,
    required Function(String verificationId) onCodeAutoRetrievalTimeout,
  }) =>
      _inner.verifyPhoneNumber(
        phoneNumber: phoneNumber,
        onCodeSent: onCodeSent,
        onVerificationCompleted: onVerificationCompleted,
        onVerificationFailed: onVerificationFailed,
        onCodeAutoRetrievalTimeout: onCodeAutoRetrievalTimeout,
      );

  @override
  Future<void> signOut() => _inner.signOut();
}
