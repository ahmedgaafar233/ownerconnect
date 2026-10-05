import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_connect/features/support/data/models/visitor_pass_model.dart';
import 'package:owner_connect/features/support/presentation/bloc/visitor_pass_bloc.dart';
import 'package:owner_connect/features/support/presentation/bloc/visitor_pass_event.dart';
import 'package:owner_connect/features/support/presentation/screens/visitor_passes_screen.dart';

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

void main() {
  testWidgets('each pass shows its status, and only an active one offers the QR code', (tester) async {
    final repository = FakeSupportRepository()
      ..passes = [
        _pass('Waiting', 'PENDING'),
        _pass('Ready', 'ACTIVE'),
        _pass('Refused', 'REJECTED', type: 'VISITOR', reason: 'Card already issued at the desk'),
      ];
    final support = VisitorPassBloc(repository: repository);
    addTearDown(support.close);

    await tester.pumpWidget(BlocProvider<VisitorPassBloc>.value(
      value: support,
      child: const MaterialApp(home: VisitorPassesScreen()),
    ));
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

    await tester.pumpWidget(BlocProvider<VisitorPassBloc>.value(
      value: support,
      child: const MaterialApp(home: VisitorPassesScreen()),
    ));
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

    await tester.pumpWidget(BlocProvider<VisitorPassBloc>.value(
      value: support,
      child: const MaterialApp(home: VisitorPassesScreen()),
    ));
    await tester.pumpAndSettle();

    repository.failNextPassFetch = true;
    support.add(const FetchVisitorPassesEvent(refresh: true));
    await tester.pumpAndSettle();

    expect(find.text('Sara'), findsOneWidget);
  });
}
