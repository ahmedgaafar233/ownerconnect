import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:owner_connect/core/router/app_router.dart';
import 'package:owner_connect/core/router/splash_gate.dart';
import 'package:owner_connect/core/theme/app_theme.dart';
import 'package:owner_connect/core/widgets/owc_mark.dart';
import 'package:owner_connect/features/auth/data/models/resort_model.dart';
import 'package:owner_connect/features/auth/data/resort_selection.dart';
import 'package:owner_connect/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:owner_connect/features/auth/presentation/screens/phone_entry_screen.dart';
import 'package:owner_connect/features/auth/presentation/screens/splash_screen.dart';

import 'support_test_fakes.dart';

const _village = ResortModel(id: 1, name: 'Delta Sharm');

ResortSelection _selection(ResortModel? resort) => ResortSelection(const FlutterSecureStorage(), resort);

/// Built inside the test body so its async work runs in the test's fake-time
/// zone (a bloc made in setUp() would never get its events processed by pump()).
AuthBloc _newAuth() => AuthBloc(repository: FakeAuthRepository({}));

Widget _app({required ResortSelection selection, required SplashGate gate, required AuthBloc auth, Widget? home}) {
  return MultiProvider(
    providers: [
      ChangeNotifierProvider.value(value: selection),
      ChangeNotifierProvider.value(value: gate),
    ],
    child: BlocProvider.value(
      value: auth,
      child: home != null
          ? MaterialApp(theme: AppTheme.lightTheme, home: home)
          : MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: AppRouter.build(auth, selection, splashGate: gate)),
    ),
  );
}

void main() {
  testWidgets('the splash is the OwnerConnect one — animated OWC monogram and wordmark — whether or not a village is known', (tester) async {
    for (final resort in [null, _village]) {
      final auth = _newAuth();
      addTearDown(auth.close);
      await tester.pumpWidget(_app(selection: _selection(resort), gate: SplashGate(), auth: auth, home: const SplashScreen()));
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.byType(OwcMark), findsOneWidget, reason: 'resort: $resort');
      expect(find.text('OWNERCONNECT'), findsOneWidget, reason: 'resort: $resort');
      // No invented village splash: the village's name is not painted on it.
      expect(find.text('DELTA SHARM'), findsNothing);
      expect(find.text('Delta Sharm'), findsNothing);
      await tester.pumpWidget(const SizedBox());
    }
  });

  testWidgets('the monogram is given long enough to finish drawing its three letters', (tester) async {
    // All three letters are drawn by 62% of the mark's cycle.
    final lettersDrawnBy = SplashScreen.markDuration * 0.62;
    expect(SplashScreen.minimumDisplay, greaterThan(lettersDrawnBy));

    final gate = SplashGate();
    final auth = _newAuth();
    addTearDown(auth.close);
    await tester.pumpWidget(_app(selection: _selection(null), gate: gate, auth: auth, home: const SplashScreen()));

    await tester.pump(lettersDrawnBy);
    expect(gate.isDone, isFalse); // still on screen once the letters are complete
    await tester.pump(SplashScreen.minimumDisplay - lettersDrawnBy + const Duration(milliseconds: 50));
    expect(gate.isDone, isTrue);
  });

  testWidgets('the router waits on the splash even though the session check is already done', (tester) async {
    final gate = SplashGate();
    final auth = _newAuth();
    addTearDown(auth.close);
    await tester.pumpWidget(_app(selection: _selection(_village), gate: gate, auth: auth));
    await tester.pump(const Duration(milliseconds: 600)); // auth has long since resolved

    expect(find.text('OWNERCONNECT'), findsOneWidget);
    expect(find.byType(PhoneEntryScreen), findsNothing);

    await tester.pump(SplashScreen.minimumDisplay);
    await tester.pumpAndSettle();
    expect(find.byType(PhoneEntryScreen), findsOneWidget);
  });

  testWidgets('leaving the splash for any reason opens the gate so the router is never stuck', (tester) async {
    final gate = SplashGate();
    final auth = _newAuth();
    addTearDown(auth.close);
    await tester.pumpWidget(_app(selection: _selection(_village), gate: gate, auth: auth, home: const SplashScreen()));
    await tester.pump(const Duration(milliseconds: 100));
    expect(gate.isDone, isFalse);

    await tester.pumpWidget(const SizedBox());
    expect(gate.isDone, isTrue);
  });
}
