import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl_phone_field/intl_phone_field.dart';

import 'package:owner_connect/core/theme/app_theme.dart';
import 'package:owner_connect/features/profile/data/models/payment_method_model.dart';
import 'package:owner_connect/features/profile/data/repositories/payment_method_repository.dart';
import 'package:owner_connect/features/profile/presentation/screens/payment_methods_screen.dart';

/// In-memory stand-in for the payment-methods API.
class FakePaymentMethodRepository implements PaymentMethodRepository {
  FakePaymentMethodRepository({List<PaymentMethodModel>? methods, this.maxMethods = 10})
      : methods = methods ?? [];

  List<PaymentMethodModel> methods;
  final int maxMethods;
  final added = <Map<String, Object?>>[];
  final removed = <int>[];
  final madeDefault = <int>[];
  String? failWith;

  @override
  Dio get dio => throw UnimplementedError();

  @override
  Future<List<PaymentMethodModel>> list() async => List.of(methods);

  @override
  Future<PaymentMethodOptions> options() async => PaymentMethodOptions(
        cardEnabled: false,
        maxMethods: maxMethods,
        walletProviders: const [WalletProvider('VODAFONE_CASH', 'Vodafone Cash'), WalletProvider('ORANGE_CASH', 'Orange Cash')],
      );

  @override
  Future<PaymentMethodModel> add({
    required String kind,
    String? walletProvider,
    String? walletPhone,
    String? instapayAddress,
    bool makeDefault = false,
  }) async {
    if (failWith != null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/x'),
        response: Response(requestOptions: RequestOptions(path: '/x'), statusCode: 400, data: {'detail': failWith}),
      );
    }
    added.add({'kind': kind, 'walletProvider': walletProvider, 'walletPhone': walletPhone, 'instapayAddress': instapayAddress});
    final method = PaymentMethodModel(
      id: methods.length + 100,
      kind: kind,
      label: kind == 'WALLET' ? 'Vodafone Cash · $walletPhone' : (kind == 'INSTAPAY' ? 'InstaPay · $instapayAddress' : 'Fawry'),
      isDefault: methods.isEmpty,
    );
    methods = [...methods, method];
    return method;
  }

  @override
  Future<void> remove(int id) async {
    removed.add(id);
    methods = methods.where((m) => m.id != id).toList();
  }

  @override
  Future<void> makeDefault(int id) async {
    madeDefault.add(id);
    methods = [for (final m in methods) PaymentMethodModel(id: m.id, kind: m.kind, label: m.label, isDefault: m.id == id)];
  }
}

Future<FakePaymentMethodRepository> _pump(WidgetTester tester, {FakePaymentMethodRepository? repository}) async {
  repository ??= FakePaymentMethodRepository();
  await tester.pumpWidget(
    RepositoryProvider<PaymentMethodRepository>.value(
      value: repository,
      // The app's own theme: its buttons are full width, which a layout must respect.
      child: MaterialApp(theme: AppTheme.lightTheme, home: const PaymentMethodsScreen()),
    ),
  );
  await tester.pumpAndSettle();
  return repository;
}

Finder get _sheet => find.byType(BottomSheet);

void main() {
  testWidgets('with nothing saved it says so, and explains that cards never go through the app', (tester) async {
    await _pump(tester);
    expect(find.text('No saved payment methods yet.'), findsOneWidget);
    expect(find.textContaining('Card details are never kept in this app'), findsOneWidget);
    expect(find.text('Add payment method'), findsOneWidget);
  });

  testWidgets('saved methods are listed, the default one marked', (tester) async {
    await _pump(
      tester,
      repository: FakePaymentMethodRepository(methods: const [
        PaymentMethodModel(id: 1, kind: 'WALLET', label: 'Vodafone Cash · +201000000101', isDefault: true),
        PaymentMethodModel(id: 2, kind: 'FAWRY', label: 'Fawry'),
      ]),
    );
    expect(find.text('Vodafone Cash · +201000000101'), findsOneWidget);
    expect(find.text('Fawry'), findsOneWidget);
    expect(find.text('Default'), findsOneWidget);
  });

  testWidgets('a bank card is shown as coming later and cannot be entered here', (tester) async {
    final repository = await _pump(tester);
    await tester.tap(find.text('Add payment method'));
    await tester.pumpAndSettle();

    expect(find.text('Bank card (Visa, Mastercard, Meeza)'), findsOneWidget);
    expect(find.textContaining('Available once online payment goes live'), findsOneWidget);
    await tester.tap(find.text('Bank card (Visa, Mastercard, Meeza)'));
    await tester.pumpAndSettle();
    expect(find.text('Wallet phone number'), findsNothing); // nothing opened
    expect(repository.added, isEmpty);
    // and no field anywhere asks for a card number
    expect(find.textContaining('Card number'), findsNothing);
  });

  testWidgets('a mobile wallet is saved with its provider and the number in international form', (tester) async {
    final repository = await _pump(tester);
    await tester.tap(find.text('Add payment method'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Mobile wallet'));
    await tester.pumpAndSettle();

    final save = find.widgetWithText(ElevatedButton, 'Save');
    expect(tester.widget<ElevatedButton>(save).onPressed, isNull); // no number yet

    await tester.tap(find.text('Orange Cash'));
    await tester.enterText(
      find.descendant(of: find.byType(IntlPhoneField), matching: find.byType(TextField)),
      '1005550001',
    );
    await tester.pump();
    await tester.tap(save);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(repository.added, [
      {'kind': 'WALLET', 'walletProvider': 'ORANGE_CASH', 'walletPhone': '+201005550001', 'instapayAddress': null},
    ]);
    expect(find.text('Payment method saved.'), findsOneWidget);
    await tester.pumpAndSettle();
    expect(find.text('Vodafone Cash · +201005550001'), findsOneWidget); // listed after the reload
  });

  testWidgets('InstaPay needs a proper address before it can be saved', (tester) async {
    final repository = await _pump(tester);
    await tester.tap(find.text('Add payment method'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('InstaPay').last);
    await tester.pumpAndSettle();

    final save = find.widgetWithText(ElevatedButton, 'Save');
    await tester.enterText(find.byType(TextField), 'not an address');
    await tester.pump();
    expect(tester.widget<ElevatedButton>(save).onPressed, isNull);

    await tester.enterText(find.byType(TextField), 'ahmed.g@instapay');
    await tester.pump();
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(repository.added.single['instapayAddress'], 'ahmed.g@instapay');
  });

  testWidgets('Fawry is saved with one tap', (tester) async {
    final repository = await _pump(tester);
    await tester.tap(find.text('Add payment method'));
    await tester.pumpAndSettle();
    await tester.tap(find.descendant(of: _sheet, matching: find.text('Fawry')));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ElevatedButton, 'Save'));
    await tester.pumpAndSettle();
    expect(repository.added.single['kind'], 'FAWRY');
  });

  testWidgets('removing a method asks first; making another the default works', (tester) async {
    final repository = await _pump(
      tester,
      repository: FakePaymentMethodRepository(methods: const [
        PaymentMethodModel(id: 1, kind: 'WALLET', label: 'Vodafone Cash · +201000000101', isDefault: true),
        PaymentMethodModel(id: 2, kind: 'FAWRY', label: 'Fawry'),
      ]),
    );

    // Fawry (not the default) can be made the default…
    await tester.tap(find.byType(PopupMenuButton<String>).last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Make default'));
    await tester.pumpAndSettle();
    expect(repository.madeDefault, [2]);

    // …and the wallet removed, after confirming.
    await tester.tap(find.byType(PopupMenuButton<String>).first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Remove').last);
    await tester.pumpAndSettle();
    expect(find.text('Remove Vodafone Cash · +201000000101?'), findsOneWidget);
    await tester.tap(find.descendant(of: find.byType(AlertDialog), matching: find.widgetWithText(TextButton, 'Remove')));
    await tester.pumpAndSettle();
    expect(repository.removed, [1]);
  });

  testWidgets("the server's reason is shown when saving is refused", (tester) async {
    final repository = FakePaymentMethodRepository()..failWith = 'You already saved this payment method.';
    await _pump(tester, repository: repository);
    await tester.tap(find.text('Add payment method'));
    await tester.pumpAndSettle();
    await tester.tap(find.descendant(of: _sheet, matching: find.text('Fawry')));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(ElevatedButton, 'Save'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('You already saved this payment method.'), findsOneWidget);
  });

  testWidgets('at the limit the add button is off and says why', (tester) async {
    await _pump(
      tester,
      repository: FakePaymentMethodRepository(
        maxMethods: 1,
        methods: const [PaymentMethodModel(id: 1, kind: 'FAWRY', label: 'Fawry', isDefault: true)],
      ),
    );
    expect(find.textContaining('most payment methods allowed'), findsOneWidget);
    // (ElevatedButton.icon is a subclass, which a plain byType finder would miss.)
    final addButton = find.ancestor(of: find.text('Add payment method'), matching: find.bySubtype<ButtonStyleButton>());
    expect(tester.widget<ButtonStyleButton>(addButton).onPressed, isNull);
  });
}
