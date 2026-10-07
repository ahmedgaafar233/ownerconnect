import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_connect/features/profile/data/models/lease_model.dart';
import 'package:owner_connect/features/profile/data/models/profile_unit.dart';
import 'package:owner_connect/features/support/presentation/widgets/pass_qr_dialog.dart';
import 'package:owner_connect/features/profile/presentation/bloc/lease_bloc.dart';
import 'package:owner_connect/features/profile/presentation/screens/lease_details_screen.dart';

import 'profile_test_fakes.dart';

const _unit = ProfileUnit(id: 88, unitKey: 'DEMO-BELL-1');

LeaseModel _lease({
  String status = 'ACTIVE',
  String balance = '200.00',
  bool cleared = false,
  List<LeaseAdultModel> adults = const [],
  List<LeaseDocumentModel> documents = const [],
  int maxAdults = 5,
  Map<String, MeterPair> meters = const {},
}) =>
    LeaseModel(
      id: 5,
      term: 'LONG',
      status: status,
      startDate: '2026-10-01',
      endDate: '2026-12-31',
      tenantName: 'Mona Tenant',
      tenantPhone: '+201005550001',
      tenantNationalId: '29001011234567',
      occupants: 3,
      tenantBalance: balance,
      tenantCleared: cleared,
      access: const LeasePass(id: 1, passCode: 'PASS-TENANT', status: 'ACTIVE'),
      adults: adults,
      documents: documents,
      maxAdults: maxAdults,
      meterReadings: meters,
    );

/// Opened from another screen, as in the app, so ending the rental has
/// somewhere to go back to.
Future<FakeLeaseRepository> _pump(WidgetTester tester, LeaseModel lease, {FakeLeaseRepository? repository}) async {
  repository ??= FakeLeaseRepository();
  final bloc = LeaseBloc(repository: repository);
  addTearDown(bloc.close);

  await tester.pumpWidget(MaterialApp(
    home: Builder(
      builder: (context) => Scaffold(
        body: TextButton(
          onPressed: () => Navigator.of(context).push(MaterialPageRoute(
            builder: (_) => BlocProvider.value(
              value: bloc,
              child: LeaseDetailsScreen(unit: _unit, lease: lease, pickPhoto: (_) async => '/no/such/id.png'),
            ),
          )),
          child: const Text('open details'),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('open details'));
  await tester.pumpAndSettle();
  return repository;
}

/// The page is a long lazily-built list; bring the QR section into view.
Future<void> _toQrSection(WidgetTester tester) =>
    tester.scrollUntilVisible(find.text('QR codes — village gate & pool'), 300);

void main() {
  testWidgets("shows the tenant and what they still owe while the rental runs", (tester) async {
    await _pump(tester, _lease());

    expect(find.text('Mona Tenant'), findsWidgets);
    expect(find.text('+201005550001'), findsOneWidget);
    expect(find.text('29001011234567'), findsOneWidget);
    expect(find.text('Tenant still owes: 200.00 EGP'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('End rental'), 300);
    expect(find.text('End rental'), findsOneWidget);
  });

  testWidgets('a zero balance mid-rental is not announced as "cleared"', (tester) async {
    await _pump(tester, _lease(balance: '0.00', cleared: true));

    expect(find.text('Tenant still owes: 0.00 EGP'), findsOneWidget);
    expect(find.textContaining('paid everything'), findsNothing);
  });

  testWidgets('once the rental is over and the tenant owes nothing, the owner is told they are cleared',
      (tester) async {
    await _pump(tester, _lease(status: 'ENDED', balance: '0.00', cleared: true));

    expect(find.textContaining('The tenant has paid everything'), findsOneWidget);
    expect(find.text('End rental'), findsNothing); // nothing left to end
  });

  testWidgets('a finished rental that still owes shows the balance, not the all-clear', (tester) async {
    await _pump(tester, _lease(status: 'ENDED'));

    expect(find.text('Tenant still owes: 200.00 EGP'), findsOneWidget);
    expect(find.textContaining('paid everything'), findsNothing);
  });

  testWidgets('ending the rental asks first, then ends it and goes back', (tester) async {
    final repository = await _pump(tester, _lease());

    await tester.scrollUntilVisible(find.text('End rental'), 300);
    await tester.tap(find.text('End rental'));
    await tester.pumpAndSettle();
    expect(find.text('End this rental?'), findsOneWidget);

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(repository.ended, isEmpty);

    await tester.tap(find.text('End rental'));
    await tester.pumpAndSettle();
    await tester.tap(find.descendant(of: find.byType(AlertDialog), matching: find.text('End rental')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(repository.ended, [5]);
    await tester.pumpAndSettle();
    expect(find.text('open details'), findsOneWidget); // back on the previous screen
  });

  testWidgets("every adult's QR is listed and can be shown", (tester) async {
    await _pump(
      tester,
      _lease(adults: const [
        LeaseAdultModel(
          id: 7,
          fullName: 'Mona Spouse',
          relation: 'SPOUSE',
          access: LeasePass(id: 2, passCode: 'PASS-SPOUSE', status: 'ACTIVE'),
        ),
      ]),
    );

    await _toQrSection(tester);
    expect(find.text('Mona Spouse'), findsOneWidget);
    expect(find.text('Show QR'), findsNWidgets(2)); // the tenant's and the spouse's
    await tester.tap(find.text('Show QR').last);
    await tester.pumpAndSettle();
    expect(find.byType(PassQrDialog), findsOneWidget);
    expect(find.textContaining('PASS-SPOUSE'), findsOneWidget);
  });

  testWidgets("a short stay tells the owner the QR codes are theirs to hand over", (tester) async {
    final lease = LeaseModel(
      id: 5,
      term: 'SHORT',
      status: 'ACTIVE',
      startDate: '2026-10-01',
      endDate: '2026-10-05',
      tenantName: 'Guest',
      access: const LeasePass(id: 1, passCode: 'PASS-G', status: 'ACTIVE'),
    );
    await _pump(tester, lease);
    await _toQrSection(tester);
    expect(find.textContaining('A short stay has no app account'), findsOneWidget);
  });

  testWidgets('an adult can be added once there is room, and not when the unit is full', (tester) async {
    final repository = await _pump(tester, _lease(maxAdults: 2));
    await tester.scrollUntilVisible(find.text('Add an adult'), 300);
    await tester.tap(find.text('Add an adult'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Full name'), 'Sam Relative');
    await tester.enterText(find.widgetWithText(TextField, 'National ID / Passport number'), '123');
    await tester.tap(find.text('Add photo'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Choose from gallery'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ElevatedButton, 'Save'));
    await tester.pumpAndSettle();
    expect(repository.addedAdults.single.fullName, 'Sam Relative');
  });

  testWidgets('a full unit cannot take another adult', (tester) async {
    await _pump(
      tester,
      _lease(maxAdults: 2, adults: const [LeaseAdultModel(id: 7, fullName: 'Mona Spouse')]),
    );
    await tester.scrollUntilVisible(find.text('Add an adult'), 300);
    expect(tester.widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Add an adult')).onPressed, isNull);
  });

  testWidgets('removing an adult asks first and stops their QR', (tester) async {
    final repository = await _pump(
      tester,
      _lease(adults: const [LeaseAdultModel(id: 7, fullName: 'Mona Spouse')]),
    );
    await _toQrSection(tester);
    await tester.tap(find.byIcon(Icons.close).first);
    await tester.pumpAndSettle();
    expect(find.text('Remove Mona Spouse? Their QR stops working.'), findsOneWidget);
    await tester.tap(find.descendant(of: find.byType(AlertDialog), matching: find.widgetWithText(TextButton, 'Remove')));
    await tester.pumpAndSettle();
    expect(repository.removedAdults, [7]);
  });

  testWidgets('extending asks for a new end date and keeps the owner on the rental', (tester) async {
    final repository = await _pump(tester, _lease());
    await tester.scrollUntilVisible(find.text('Extend'), 300);
    await tester.tap(find.text('Extend'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('OK'));
    await tester.pumpAndSettle();

    expect(repository.extended, ['2027-01-30']); // 30 days past the current end, 2026-12-31
    expect(find.text('Extend'), findsOneWidget); // still on the rental's page, not thrown back
    expect(find.text('Rental extended. The QR codes stay valid.'), findsOneWidget);
  });

  testWidgets('a new period keeps the same people and goes back to the profile', (tester) async {
    final repository = await _pump(tester, _lease(status: 'ENDED'));
    await tester.scrollUntilVisible(find.text('New period'), 300);
    await tester.tap(find.text('New period'));
    await tester.pumpAndSettle();
    expect(find.text('Same tenant, same people and the same QR codes — only the dates change.'), findsOneWidget);
    await tester.tap(find.descendant(of: find.byType(AlertDialog), matching: find.text('New period')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(repository.renewed, hasLength(1));
    expect(repository.renewed.single['term'], 'LONG');
    await tester.pumpAndSettle();
    expect(find.text('open details'), findsOneWidget);
  });

  testWidgets('papers sent to the village are listed and can be removed', (tester) async {
    final repository = await _pump(
      tester,
      _lease(documents: const [LeaseDocumentModel(id: 3, kind: 'MARRIAGE_CERT', label: '')]),
    );
    await tester.scrollUntilVisible(find.text('Marriage certificate'), 300);
    await tester.tap(find.byIcon(Icons.close).last);
    await tester.pumpAndSettle();
    await tester.tap(find.descendant(of: find.byType(AlertDialog), matching: find.widgetWithText(TextButton, 'Remove')));
    await tester.pumpAndSettle();
    expect(repository.removedDocuments, [3]);
  });

  testWidgets('shows the meter readings Maintenance took, and what is still waiting to be read', (tester) async {
    await _pump(
      tester,
      _lease(meters: const {
        'ELECTRICITY': MeterPair(entry: MeterReadingValue(reading: '1500.50', readOn: '2026-10-01')),
        'WATER': MeterPair(),
      }),
    );
    await tester.scrollUntilVisible(find.text('Meter readings'), 300);
    expect(find.textContaining('1500.50'), findsOneWidget);
    expect(find.text('Not read yet'), findsNWidgets(3)); // electricity exit, water entry, water exit
    expect(find.textContaining('Maintenance team'), findsOneWidget);
  });
}
