import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_connect/features/support/presentation/bloc/support_bloc.dart';
import 'package:owner_connect/features/support/presentation/screens/support_tickets_screen.dart';

import 'support_test_fakes.dart';

void main() {
  testWidgets('the Support & Maintenance list leaves out the pay-at-the-office notes', (tester) async {
    // Those are ACCOUNTS tickets that belong to the payment flow; showing them
    // here put "I'll pay cash at the office" entries among maintenance requests.
    final repository = FakeSupportRepository();
    final support = SupportBloc(repository: repository);
    addTearDown(support.close);

    await tester.pumpWidget(BlocProvider<SupportBloc>.value(
      value: support,
      child: const MaterialApp(home: SupportTicketsScreen()),
    ));
    await tester.pumpAndSettle();

    expect(repository.requestedExcludeCategories, ['ACCOUNTS']);
  });
}
