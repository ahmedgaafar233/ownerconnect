import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_connect/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:owner_connect/features/support/presentation/bloc/support_bloc.dart';
import 'package:owner_connect/features/support/presentation/screens/new_support_request_screen.dart';

import 'support_test_fakes.dart';

Future<FakeSupportRepository> _pumpForm(WidgetTester tester, {required String role}) async {
  final auth = AuthBloc(
    repository: FakeAuthRepository({
      'id': 1,
      'role': role,
      'units': [
        {'id': 7, 'unit_key': '1/101'},
      ],
    }),
  );
  final repository = FakeSupportRepository();
  final support = SupportBloc(repository: repository);
  addTearDown(auth.close);
  addTearDown(support.close);

  await tester.pumpWidget(MultiBlocProvider(
    providers: [
      BlocProvider<AuthBloc>.value(value: auth),
      BlocProvider<SupportBloc>.value(value: support),
    ],
    child: const MaterialApp(home: NewSupportRequestScreen()),
  ));
  await tester.pumpAndSettle();
  return repository;
}

Future<void> _submit(WidgetTester tester) async {
  // The test viewport is small; the button sits below the type grid.
  await tester.ensureVisible(find.text('Submit Request'));
  await tester.tap(find.text('Submit Request'));
  await tester.pump();
}

void main() {
  testWidgets('an Owner picking Electrician sends the ELECTRICIAN service type under MAINTENANCE', (tester) async {
    final repository = await _pumpForm(tester, role: 'OWNER');

    await tester.tap(find.text('Electrician'));
    await tester.pump();
    await _submit(tester);

    expect(repository.createdTickets, [
      {'unitId': 7, 'category': 'MAINTENANCE', 'serviceType': 'ELECTRICIAN', 'subject': 'Electrician'},
    ]);
  });

  testWidgets('an Owner can raise a housekeeping request, filed under the HOUSEKEEPING category', (tester) async {
    final repository = await _pumpForm(tester, role: 'OWNER');

    await tester.ensureVisible(find.text('Housekeeping'));
    await tester.tap(find.text('Housekeeping'));
    await tester.pump();
    await _submit(tester);

    expect(repository.createdTickets.single['category'], 'HOUSEKEEPING');
    expect(repository.createdTickets.single['serviceType'], 'HOUSEKEEPING');
  });

  testWidgets('a Tenant is not offered housekeeping — maintenance requests only', (tester) async {
    await _pumpForm(tester, role: 'TENANT');

    expect(find.text('Electrician'), findsOneWidget);
    expect(find.text('Housekeeping'), findsNothing);
  });
}
