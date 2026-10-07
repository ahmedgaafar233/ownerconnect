import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl_phone_field/intl_phone_field.dart';

import 'package:owner_connect/features/profile/data/models/profile_unit.dart';
import 'package:owner_connect/features/profile/presentation/bloc/lease_bloc.dart';
import 'package:owner_connect/features/profile/presentation/screens/rent_out_screen.dart';

import 'profile_test_fakes.dart';

const _unit = ProfileUnit(id: 88, unitKey: 'DEMO-BELL-1');

/// The form opened from another screen, as in the app, so a successful
/// submit has somewhere to go back to.
Future<FakeLeaseRepository> _pump(WidgetTester tester) async {
  final repository = FakeLeaseRepository();
  final bloc = LeaseBloc(repository: repository);
  addTearDown(bloc.close);

  await tester.pumpWidget(MaterialApp(
    home: Builder(
      builder: (context) => Scaffold(
        body: TextButton(
          onPressed: () => Navigator.of(context).push(MaterialPageRoute(
            builder: (_) => BlocProvider.value(
              value: bloc,
              child: RentOutScreen(unit: _unit, pickPhoto: (_) async => '/no/such/id.png'),
            ),
          )),
          child: const Text('open form'),
        ),
      ),
    ),
  ));
  await tester.tap(find.text('open form'));
  await tester.pumpAndSettle();
  return repository;
}

Finder get _submit => find.widgetWithText(ElevatedButton, 'Register rental');

Future<void> _fillTenant(WidgetTester tester, {bool withPhoto = true}) async {
  await tester.enterText(find.widgetWithText(TextField, "Tenant's full name"), 'Mona Tenant');
  await tester.enterText(
    find.descendant(of: find.byType(IntlPhoneField), matching: find.byType(TextField)),
    '1005550001',
  );
  await tester.enterText(find.widgetWithText(TextField, 'National ID / Passport number'), '29001011234567');
  if (withPhoto) {
    await tester.ensureVisible(find.text('Add photo'));
    await tester.tap(find.text('Add photo'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Choose from gallery'));
    await tester.pumpAndSettle();
  }
  await tester.pump();
}

Finder get _sheet => find.byType(BottomSheet);

void main() {
  testWidgets('cannot be submitted until the tenant, phone, ID number and ID photo are all given', (tester) async {
    await _pump(tester);
    expect(tester.widget<ElevatedButton>(_submit).onPressed, isNull);

    await _fillTenant(tester, withPhoto: false);
    expect(tester.widget<ElevatedButton>(_submit).onPressed, isNull); // still no photo

    await tester.ensureVisible(find.text('Add photo'));
    await tester.tap(find.text('Add photo'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Choose from gallery'));
    await tester.pumpAndSettle();
    expect(tester.widget<ElevatedButton>(_submit).onPressed, isNotNull);
  });

  testWidgets('a short stay is registered straight away, with the number in international form', (tester) async {
    final repository = await _pump(tester);
    await _fillTenant(tester);

    await tester.ensureVisible(_submit);
    await tester.tap(_submit);
    await tester.pumpAndSettle();

    expect(repository.created, hasLength(1));
    final sent = repository.created.single;
    expect(sent['unitId'], 88);
    expect(sent['term'], 'SHORT');
    expect(sent['tenantPhone'], '+201005550001'); // not 0100…, not 00 20…
    expect(sent['tenantName'], 'Mona Tenant');
    expect(sent['tenantNationalId'], '29001011234567');
    expect(sent['idPhotoPath'], '/no/such/id.png');
    expect(sent['occupants'], 1);
    expect(find.text('open form'), findsOneWidget); // form closed
  });

  testWidgets('a long-term rental asks before moving water & electricity, and sends nothing if declined',
      (tester) async {
    final repository = await _pump(tester);
    await tester.tap(find.text('Long-term'));
    await tester.pump();
    expect(find.textContaining('charged to the tenant'), findsOneWidget);
    await _fillTenant(tester);

    await tester.ensureVisible(_submit);
    await tester.tap(_submit);
    await tester.pumpAndSettle();
    expect(find.text('Move water & electricity to the tenant?'), findsOneWidget);

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(repository.created, isEmpty);

    await tester.ensureVisible(_submit);
    await tester.tap(_submit);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm'));
    await tester.pumpAndSettle();
    expect(repository.created.single['term'], 'LONG');
  });

  testWidgets("the server's own reason is shown when it refuses", (tester) async {
    final repository = await _pump(tester);
    repository.failWith = {
      'tenant_phone': ['This phone number already belongs to another account.'],
    };
    await _fillTenant(tester);

    await tester.ensureVisible(_submit);
    await tester.tap(_submit);
    await tester.pumpAndSettle();

    expect(find.text('This phone number already belongs to another account.'), findsOneWidget);
    expect(find.text('Register rental'), findsWidgets); // still on the form
  });
}


void main2() {
  testWidgets('every other adult is added with their ID and gets uploaded after the rental is registered', (tester) async {
    final repository = await _pump(tester);
    await _fillTenant(tester);

    await tester.ensureVisible(find.text('Add an adult'));
    await tester.tap(find.text('Add an adult'));
    await tester.pumpAndSettle();
    expect(find.text('Spouse'), findsOneWidget);

    await tester.enterText(find.descendant(of: _sheet, matching: find.widgetWithText(TextField, 'Full name')), 'Mona Spouse');
    await tester.enterText(
      find.descendant(of: _sheet, matching: find.widgetWithText(TextField, 'National ID / Passport number')),
      '29001019999999',
    );
    await tester.tap(find.descendant(of: _sheet, matching: find.text('Add photo')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Choose from gallery'));
    await tester.pumpAndSettle();
    await tester.tap(find.descendant(of: _sheet, matching: find.text('Save')));
    await tester.pumpAndSettle();

    expect(find.text('Mona Spouse'), findsOneWidget); // listed on the form

    await tester.ensureVisible(_submit);
    await tester.tap(_submit);
    await tester.pumpAndSettle();

    expect(repository.created, hasLength(1));
    expect(repository.addedAdults, hasLength(1));
    expect(repository.addedAdults.single.fullName, 'Mona Spouse');
    expect(repository.addedAdults.single.relation, 'SPOUSE');
    expect(repository.addedAdults.single.photoPath, '/no/such/id.png');
  });

  testWidgets('a unit only has room for as many adults as its size allows', (tester) async {
    final repository = FakeLeaseRepository();
    final bloc = LeaseBloc(repository: repository);
    addTearDown(bloc.close);
    await tester.pumpWidget(MaterialApp(
      home: BlocProvider.value(
        value: bloc,
        child: RentOutScreen(
          unit: const ProfileUnit(id: 88, unitKey: 'DEMO-BELL-1', cardAllowance: 1), // just the tenant
          pickPhoto: (_) async => '/no/such/id.png',
        ),
      ),
    ));
    await tester.ensureVisible(find.text('Add an adult'));
    expect(tester.widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Add an adult')).onPressed, isNull);
    expect(find.text('This unit has room for 1 adults, the tenant included.'), findsOneWidget);
  });

  testWidgets('papers for Security can be added and taken back off the form', (tester) async {
    final repository = await _pump(tester);
    await _fillTenant(tester);

    await tester.ensureVisible(find.text('Add a paper'));
    await tester.tap(find.text('Add a paper'));
    await tester.pumpAndSettle();
    await tester.tap(find.descendant(of: _sheet, matching: find.text('Marriage certificate')));
    await tester.tap(find.descendant(of: _sheet, matching: find.text('Add photo')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Choose from gallery'));
    await tester.pumpAndSettle();
    await tester.tap(find.descendant(of: _sheet, matching: find.text('Save')));
    await tester.pumpAndSettle();

    expect(find.text('Marriage certificate'), findsOneWidget); // listed on the form

    await tester.ensureVisible(_submit);
    await tester.tap(_submit);
    await tester.pumpAndSettle();
    expect(repository.addedDocuments.single.kind, 'MARRIAGE_CERT');
  });
}
