import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_connect/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:owner_connect/features/auth/presentation/bloc/auth_event.dart';
import 'package:owner_connect/features/auth/presentation/bloc/auth_state.dart';
import 'package:owner_connect/features/financial/presentation/bloc/financial_bloc.dart';
import 'package:owner_connect/features/profile/data/repositories/lease_repository.dart';
import 'package:owner_connect/features/profile/presentation/screens/profile_screen.dart';

import 'financial_test_fakes.dart';
import 'profile_test_fakes.dart';

Future<AuthBloc> _pump(WidgetTester tester, ProfileFakeAuthRepository auth) async {
  final authBloc = AuthBloc(repository: auth);
  final financial = FinancialBloc(repository: FakeFinancialRepository());
  addTearDown(authBloc.close);
  addTearDown(financial.close);
  authBloc.add(const AuthCheckRequested());
  await authBloc.stream.firstWhere((s) => s is AuthenticatedState);

  await tester.pumpWidget(
    RepositoryProvider<LeaseRepository>.value(
      value: FakeLeaseRepository(),
      child: MultiBlocProvider(
        providers: [
          BlocProvider<AuthBloc>.value(value: authBloc),
          BlocProvider<FinancialBloc>.value(value: financial),
        ],
        child: const MaterialApp(home: ProfileScreen()),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return authBloc;
}

void main() {
  testWidgets('shows who the person is, their village, and every unit they have', (tester) async {
    await _pump(tester, ProfileFakeAuthRepository(ownerProfile()));

    expect(find.text('Ahmed Gaafar'), findsOneWidget);
    expect(find.text('AG'), findsOneWidget); // initials avatar
    expect(find.text('Owner'), findsOneWidget);
    expect(find.text('+201001234567'), findsOneWidget);
    expect(find.text('Delta Sharm'), findsOneWidget);

    expect(find.text('My units'), findsOneWidget);
    expect(find.text('2 units'), findsOneWidget);
    expect(find.text('DEMO-BELL-1'), findsOneWidget);
    expect(find.text('DEMO-BELL-2'), findsOneWidget);
    expect(find.text('Studio'), findsOneWidget);
    expect(find.text('B2 · 12'), findsOneWidget);
    expect(find.text('Access cards: 2 / 2'), findsOneWidget);
  });

  testWidgets('an unrented unit offers to rent it out; a rented one shows its tenant', (tester) async {
    await _pump(tester, ProfileFakeAuthRepository(ownerProfile()));

    expect(find.text('Rent out'), findsOneWidget); // only DEMO-BELL-1
    expect(find.text('Rented to Mona Tenant'), findsOneWidget); // DEMO-BELL-2
    expect(find.text('Rented'), findsOneWidget); // its status badge
  });

  testWidgets('saving a new name reaches the signed-in state, so the drawer stops showing the old one',
      (tester) async {
    final auth = ProfileFakeAuthRepository(ownerProfile(fullname: ''));
    final authBloc = await _pump(tester, auth);

    // No name yet: the phone number stands in, in the drawer's state and on screen.
    expect((authBloc.state as AuthenticatedState).displayName, '+201001234567');

    await tester.tap(find.byIcon(Icons.edit_outlined));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), 'Ahmed Mohamed');
    await tester.pump(); // Save is disabled until the field has a name
    await tester.tap(find.text('Save'));
    // Not pumpAndSettle: that would run the clock past the snackbar's 4 seconds.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 300));

    expect(auth.savedNames, ['Ahmed Mohamed']);
    expect(find.text('Profile updated.'), findsOneWidget);
    await tester.pumpAndSettle();
    expect(find.text('Ahmed Mohamed'), findsOneWidget);
    expect((authBloc.state as AuthenticatedState).displayName, 'Ahmed Mohamed');
  });

  testWidgets('an ended rental stays on the unit and the unit can be rented out again', (tester) async {
    final profile = ownerProfile(units: [
      {
        'id': 88,
        'unit_key': 'DEMO-BELL-1',
        'relation': 'OWNER',
        'lease': {
          'id': 5,
          'term': 'LONG',
          'status': 'ENDED',
          'start_date': '2026-06-01',
          'end_date': '2026-08-31',
          'tenant_name': 'Mona Tenant',
          'tenant_balance': '0.00',
          'tenant_cleared': true,
        },
      },
    ]);
    await _pump(tester, ProfileFakeAuthRepository(profile));

    expect(find.text('Rented to Mona Tenant'), findsOneWidget);
    expect(find.text('Ended'), findsOneWidget);
    expect(find.text('Rent out'), findsOneWidget);
  });

  testWidgets("a tenant sees their lease period and no 'Rent out' button", (tester) async {
    final profile = ownerProfile(units: [
      {
        'id': 88,
        'unit_key': 'DEMO-BELL-1',
        'relation': 'TENANT',
        'lease': {'status': 'ENDED', 'start_date': '2026-08-01', 'end_date': '2026-09-30'},
      },
    ])..['role'] = 'TENANT';
    await _pump(tester, ProfileFakeAuthRepository(profile));

    expect(find.text('Tenant'), findsWidgets);
    expect(find.text('Rent out'), findsNothing);
    expect(find.textContaining('Lease period:'), findsOneWidget);
    expect(find.text('Your lease has ended. Pay what is left to get your clearance statement.'), findsOneWidget);
  });

  testWidgets('a person with no units is told so', (tester) async {
    await _pump(tester, ProfileFakeAuthRepository(ownerProfile(units: [])));
    expect(find.text('No units are linked to your account yet.'), findsOneWidget);
  });
}
