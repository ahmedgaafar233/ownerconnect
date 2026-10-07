import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_connect/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:owner_connect/features/auth/presentation/bloc/auth_event.dart';
import 'package:owner_connect/features/auth/presentation/bloc/auth_state.dart';
import 'package:owner_connect/features/support/data/models/visitor_pass_model.dart';
import 'package:owner_connect/features/support/presentation/bloc/visitor_pass_bloc.dart';
import 'package:owner_connect/features/support/presentation/bloc/visitor_pass_event.dart';
import 'package:owner_connect/features/support/presentation/screens/visitor_passes_screen.dart';

import 'profile_test_fakes.dart';
import 'support_test_fakes.dart';

VisitorPassModel _pass(String name, String status, {String type = 'BEACH_ACCESS', String reason = ''}) =>
    VisitorPassModel.fromJson({
      'id': name.hashCode,
      'unit': 7,
      'unit_key': '1/101',
      'pass_type': type,
      'visitor_name': name,
      'status': status,
      'rejection_reason': reason,
    });

/// The pass screen as the app builds it: the pass list plus the signed-in
/// person (a long-term tenant sees their stay dates above their QR codes).
Widget _app(VisitorPassBloc support, {AuthBloc? auth}) {
  return MultiBlocProvider(
    providers: [
      BlocProvider<VisitorPassBloc>.value(value: support),
      BlocProvider<AuthBloc>.value(value: auth ?? AuthBloc(repository: ProfileFakeAuthRepository(ownerProfile()))),
    ],
    child: const MaterialApp(home: VisitorPassesScreen()),
  );
}

void main() {
  testWidgets("a long-term tenant sees their stay dates above their QR codes", (tester) async {
    final profile = ownerProfile(units: [
      {
        'id': 88,
        'unit_key': 'DEMO-BELL-1',
        'relation': 'TENANT',
        'lease': {
          'status': 'ACTIVE',
          'start_date': '2026-10-01',
          'end_date': '2026-12-31',
          'meter_readings': {
            'ELECTRICITY': {'entry': {'reading': '1500.50', 'read_on': '2026-10-01'}, 'exit': null},
            'WATER': {'entry': null, 'exit': null},
          },
        },
      },
    ])..['role'] = 'TENANT';
    final auth = AuthBloc(repository: ProfileFakeAuthRepository(profile));
    addTearDown(auth.close);
    auth.add(const AuthCheckRequested());
    await auth.stream.firstWhere((s) => s is AuthenticatedState);

    final support = VisitorPassBloc(repository: FakeSupportRepository()..passes = [_pass('Mona', 'ACTIVE', type: 'TENANT')]);
    addTearDown(support.close);

    await tester.pumpWidget(_app(support, auth: auth));
    await tester.pumpAndSettle();

    expect(find.text('Your stay · DEMO-BELL-1'), findsOneWidget);
    expect(find.textContaining('Lease period:'), findsOneWidget);
    expect(find.text('Show these QR codes at the village gate and the pool.'), findsOneWidget);
    // While they live there only the entry readings matter to them.
    expect(find.textContaining('1500.50'), findsOneWidget);
    expect(find.text('At exit'), findsNothing);
    expect(find.text('Mona'), findsOneWidget);
    expect(find.text('Show Entry QR Code'), findsOneWidget);
  });

  testWidgets('an owner sees no stay card', (tester) async {
    final support = VisitorPassBloc(repository: FakeSupportRepository()..passes = []);
    addTearDown(support.close);
    await tester.pumpWidget(_app(support));
    await tester.pumpAndSettle();
    expect(find.textContaining('Your stay'), findsNothing);
  });

  testWidgets('each pass shows its status, and only an active one offers the QR code', (tester) async {
    final repository = FakeSupportRepository()
      ..passes = [
        _pass('Waiting', 'PENDING'),
        _pass('Ready', 'ACTIVE'),
        _pass('Refused', 'REJECTED', type: 'VISITOR', reason: 'Card already issued at the desk'),
      ];
    final support = VisitorPassBloc(repository: repository);
    addTearDown(support.close);

    await tester.pumpWidget(_app(support));
    await tester.pumpAndSettle();

    expect(find.text('Awaiting Security approval'), findsOneWidget);
    expect(find.text('Active'), findsOneWidget);
    expect(find.text('Rejected'), findsOneWidget);
    expect(find.text('Card already issued at the desk'), findsOneWidget);
    // Three passes, one of them usable at the gate.
    expect(find.text('Show Entry QR Code'), findsOneWidget);
  });

  testWidgets('pulling down reloads the list in place — a decision made while it was open shows up', (tester) async {
    final repository = FakeSupportRepository()..passes = [_pass('Sara', 'PENDING')];
    final support = VisitorPassBloc(repository: repository);
    addTearDown(support.close);

    await tester.pumpWidget(_app(support));
    await tester.pumpAndSettle();
    expect(find.text('Awaiting Security approval'), findsOneWidget);

    // Security approves it while the list is on screen.
    repository.passes = [_pass('Sara', 'ACTIVE')];
    await tester.drag(find.text('Sara'), const Offset(0, 400));
    await tester.pumpAndSettle();

    expect(find.text('Awaiting Security approval'), findsNothing);
    expect(find.text('Show Entry QR Code'), findsOneWidget);
  });

  testWidgets('a refresh that fails keeps showing the list rather than an error', (tester) async {
    final repository = FakeSupportRepository()..passes = [_pass('Sara', 'ACTIVE')];
    final support = VisitorPassBloc(repository: repository);
    addTearDown(support.close);

    await tester.pumpWidget(_app(support));
    await tester.pumpAndSettle();

    repository.failNextPassFetch = true;
    support.add(const FetchVisitorPassesEvent(refresh: true));
    await tester.pumpAndSettle();

    expect(find.text('Sara'), findsOneWidget);
  });
}
