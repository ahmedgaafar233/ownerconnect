import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_connect/core/widgets/pdf_viewer_screen.dart';
import 'package:owner_connect/features/financial/presentation/bloc/financial_bloc.dart';
import 'package:owner_connect/features/financial/presentation/screens/charges_screen.dart';
import 'package:owner_connect/features/financial/presentation/screens/payment_history_screen.dart';

import 'financial_test_fakes.dart';

Future<FakeFinancialRepository> _pump(WidgetTester tester, Widget home) async {
  final repository = FakeFinancialRepository()
    ..charges = [fakeCharge(1), fakeCharge(2, unit: 'DEMO-BELL-2', type: 'ELECTRICITY')]
    ..payments = [fakePayment(90)];
  final bloc = FinancialBloc(repository: repository);
  addTearDown(bloc.close);

  await tester.pumpWidget(BlocProvider<FinancialBloc>.value(
    value: bloc,
    child: MaterialApp(home: home),
  ));
  await tester.pumpAndSettle();
  return repository;
}

void main() {
  testWidgets('opening Payment History and coming back leaves the charges page intact', (tester) async {
    // The bug: both screens shared one bloc, so loading the history replaced
    // the charges state and the charges page came back blank.
    await _pump(
      tester,
      Builder(
        builder: (context) => Stack(
          children: [
            const ChargesScreen(),
            Positioned(
              bottom: 0,
              child: TextButton(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PaymentHistoryScreen())),
                child: const Text('open history'),
              ),
            ),
          ],
        ),
      ),
    );
    expect(find.text('Unit DEMO-BELL-1'), findsWidgets);

    await tester.tap(find.text('open history'));
    await tester.pumpAndSettle();
    expect(find.textContaining('REC-DEMO-1'), findsOneWidget);

    Navigator.of(tester.element(find.byType(PaymentHistoryScreen))).pop();
    await tester.pumpAndSettle();

    expect(find.text('Unit DEMO-BELL-1'), findsWidgets);
    expect(find.text('Unit DEMO-BELL-2'), findsWidgets);
  });

  testWidgets('tapping a payment opens its receipt inside the app', (tester) async {
    final repository = await _pump(tester, const PaymentHistoryScreen());

    await tester.tap(find.textContaining('REC-DEMO-1'));
    await tester.pumpAndSettle();

    expect(find.byType(PdfViewerScreen), findsOneWidget);
    expect(repository.downloadedUrls, ['http://host/api/payments/90/receipt/']);
  });

  testWidgets('a receipt that fails to load shows a message and a retry, not a blank page', (tester) async {
    final repository = await _pump(tester, const PaymentHistoryScreen());

    await tester.tap(find.textContaining('REC-DEMO-1'));
    await tester.pumpAndSettle();

    expect(find.textContaining("Couldn't load the document"), findsOneWidget);
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();
    expect(repository.downloadedUrls.length, 2);
  });

  testWidgets('a payment with no receipt on file is not tappable', (tester) async {
    final repository = FakeFinancialRepository()..payments = [fakePayment(91, receiptNo: 'REC-NONE', url: null)];
    final bloc = FinancialBloc(repository: repository);
    addTearDown(bloc.close);
    await tester.pumpWidget(BlocProvider<FinancialBloc>.value(
      value: bloc,
      child: const MaterialApp(home: PaymentHistoryScreen()),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.textContaining('REC-NONE'));
    await tester.pumpAndSettle();
    expect(find.byType(PdfViewerScreen), findsNothing);
  });
}
