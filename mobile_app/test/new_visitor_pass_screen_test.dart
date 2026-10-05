import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_connect/core/network/api_error.dart';
import 'package:owner_connect/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:owner_connect/features/support/presentation/bloc/visitor_pass_bloc.dart';
import 'package:owner_connect/features/support/presentation/screens/new_visitor_pass_screen.dart';

import 'support_test_fakes.dart';

Map<String, dynamic> _profile({required String role, int? allowance, int used = 0}) => {
      'id': 1,
      'role': role,
      'units': [
        {'id': 7, 'unit_key': '1/101', 'card_allowance': allowance, 'cards_used': used},
      ],
    };

Future<FakeSupportRepository> _pumpForm(WidgetTester tester, Map<String, dynamic> profile) async {
  final auth = AuthBloc(repository: FakeAuthRepository(profile));
  final supportRepository = FakeSupportRepository();
  final support = VisitorPassBloc(repository: supportRepository);
  addTearDown(auth.close);
  addTearDown(support.close);

  await tester.pumpWidget(MultiBlocProvider(
    providers: [
      BlocProvider<AuthBloc>.value(value: auth),
      BlocProvider<VisitorPassBloc>.value(value: support),
    ],
    child: const MaterialApp(home: NewVisitorPassScreen()),
  ));
  await tester.pumpAndSettle();
  return supportRepository;
}

Finder get _submitButton => find.widgetWithText(ElevatedButton, 'Create Pass');

/// The form opened from another screen, as in the app, so closing it after a
/// successful submit has somewhere to go back to.
Future<FakeSupportRepository> _pumpFormOnTopOfAScreen(
  WidgetTester tester,
  Map<String, dynamic> profile, {
  required String createdPassStatus,
}) async {
  final auth = AuthBloc(repository: FakeAuthRepository(profile));
  final repository = FakeSupportRepository()..createdPassStatus = createdPassStatus;
  final support = VisitorPassBloc(repository: repository);
  addTearDown(auth.close);
  addTearDown(support.close);

  await tester.pumpWidget(MultiBlocProvider(
    providers: [
      BlocProvider<AuthBloc>.value(value: auth),
      BlocProvider<VisitorPassBloc>.value(value: support),
    ],
    child: MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: TextButton(
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const NewVisitorPassScreen())),
            child: const Text('open form'),
          ),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('open form'));
  await tester.pumpAndSettle();
  return repository;
}

void main() {
  testWidgets('an Owner whose unit is out of cards cannot submit a beach card', (tester) async {
    await _pumpForm(tester, _profile(role: 'OWNER', allowance: 2, used: 2));

    expect(find.text('Cards used: 2 / 2'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, 'Sara');
    await tester.pump();

    expect(tester.widget<ElevatedButton>(_submitButton).onPressed, isNull);
  });

  testWidgets('a guest pass is not drawn from the card allowance, even when it is used up', (tester) async {
    await _pumpForm(tester, _profile(role: 'OWNER', allowance: 2, used: 2));

    await tester.tap(find.text('Guest Pass'));
    await tester.pump(); // let the form re-lay-out before typing, as a person would
    await tester.enterText(find.byType(TextField).first, 'Sara');
    await tester.pump();

    expect(find.textContaining('Cards used'), findsNothing);
    expect(tester.widget<ElevatedButton>(_submitButton).onPressed, isNotNull);
  });

  testWidgets('with cards left, submitting sends a beach-access pass for the unit', (tester) async {
    final repository = await _pumpForm(tester, _profile(role: 'OWNER', allowance: 3, used: 1));

    expect(find.text('Cards used: 1 / 3'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, 'Sara');
    await tester.pump();
    await tester.tap(_submitButton);
    await tester.pump();

    final sent = repository.createdPasses.single;
    expect([sent['unitId'], sent['passType'], sent['visitorName']], [7, 'BEACH_ACCESS', 'Sara']);
    // Plain calendar dates — the server owns the time zone.
    expect(sent['startDate'], matches(RegExp(r'^\d{4}-\d{2}-\d{2}$')));
    expect(sent['endDate'], matches(RegExp(r'^\d{4}-\d{2}-\d{2}$')));
  });

  testWidgets('a guest pass takes a single visit date — overnight is a rental, not a visit', (tester) async {
    final repository = await _pumpForm(tester, _profile(role: 'OWNER', allowance: 3, used: 0));

    await tester.tap(find.text('Guest Pass'));
    await tester.pump();
    expect(find.text('Visit date'), findsOneWidget);
    expect(find.text('Valid until'), findsNothing);

    await tester.enterText(find.byType(TextField).first, 'Sara');
    await tester.pump();
    await tester.ensureVisible(_submitButton);
    await tester.tap(_submitButton);
    await tester.pump();
    final sent = repository.createdPasses.single;
    expect(sent['startDate'], sent['endDate']);
  });

  testWidgets('a card takes a from–to date range', (tester) async {
    await _pumpForm(tester, _profile(role: 'OWNER', allowance: 3, used: 0));

    expect(find.text('Valid from'), findsOneWidget);
    expect(find.text('Valid until'), findsOneWidget);
    expect(find.text('Visit date'), findsNothing);
  });

  testWidgets('where Security approves passes, submitting says the request was sent — not that a pass exists', (tester) async {
    await _pumpFormOnTopOfAScreen(tester, _profile(role: 'OWNER', allowance: 3, used: 0), createdPassStatus: 'PENDING');

    await tester.enterText(find.byType(TextField).first, 'Sara');
    await tester.pump();
    await tester.ensureVisible(_submitButton);
    await tester.tap(_submitButton);
    await tester.pumpAndSettle();

    expect(find.textContaining('Request sent to Security'), findsOneWidget);
    expect(find.text('Pass created'), findsNothing);
  });

  testWidgets('where owners self-issue, submitting says the pass was created', (tester) async {
    await _pumpFormOnTopOfAScreen(tester, _profile(role: 'OWNER', allowance: 3, used: 0), createdPassStatus: 'ACTIVE');

    await tester.enterText(find.byType(TextField).first, 'Sara');
    await tester.pump();
    await tester.ensureVisible(_submitButton);
    await tester.tap(_submitButton);
    await tester.pumpAndSettle();

    expect(find.text('Pass created'), findsOneWidget);
  });

  testWidgets('a unit with no allowance set shows no card counter and is unrestricted', (tester) async {
    await _pumpForm(tester, _profile(role: 'OWNER', allowance: null));

    expect(find.textContaining('Cards used'), findsNothing);
    await tester.enterText(find.byType(TextField).first, 'Sara');
    await tester.pump();
    expect(tester.widget<ElevatedButton>(_submitButton).onPressed, isNotNull);
  });

  testWidgets('a Tenant is only offered the beach card, not guest or worker passes', (tester) async {
    await _pumpForm(tester, _profile(role: 'TENANT', allowance: 2, used: 0));

    expect(find.byType(ChoiceChip), findsNothing);
    expect(find.text('Guest Pass'), findsNothing);
    expect(find.text('Cards used: 0 / 2'), findsOneWidget);
  });

  group('apiErrorMessage', () {
    DioException dioError(dynamic data) => DioException(
          requestOptions: RequestOptions(path: '/x'),
          response: Response(requestOptions: RequestOptions(path: '/x'), statusCode: 400, data: data),
        );

    test('pulls the first message out of a DRF field-error body', () {
      expect(apiErrorMessage(dioError({'unit': ['Allowance used up.']})), 'Allowance used up.');
    });

    test('reads a detail string', () {
      expect(apiErrorMessage(dioError({'detail': 'Nope.'})), 'Nope.');
    });

    test('does not dump an HTML error page', () {
      final message = apiErrorMessage(dioError('<html>${'x' * 400}</html>'));
      expect(message, isNot(contains('<html>')));
    });
  });
}
