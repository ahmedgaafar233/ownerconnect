import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import 'package:owner_connect/core/services/notification_router.dart';
import 'package:owner_connect/features/home/presentation/bloc/home_tab_bloc.dart';
import 'package:owner_connect/features/home/presentation/bloc/home_tab_state.dart';

void main() {
  group('notificationTarget', () {
    NotificationTarget target(String type, {String enumType = ''}) =>
        notificationTarget({'type': type}, type: enumType);

    test('billing notifications open the charges tab', () {
      for (final type in ['charges_published', 'payment_deferred', 'unit_payment_deferred', 'payment_plan_decided']) {
        expect(target(type), NotificationTarget.charges, reason: type);
      }
    });

    test('a payment received opens the payment history', () {
      expect(target('payment_success'), NotificationTarget.paymentHistory);
      expect(target('unit_payment_success'), NotificationTarget.paymentHistory);
    });

    test('service request updates open the support tab and pass decisions the passes tab', () {
      expect(target('ticket_reply'), NotificationTarget.support);
      expect(target('ticket_status'), NotificationTarget.support);
      expect(target('pass_decided'), NotificationTarget.passes);
    });

    test('falls back to the inbox row type when the payload has none', () {
      expect(notificationTarget(const {}, type: 'PASS_DECIDED'), NotificationTarget.passes);
      expect(notificationTarget(const {}, type: 'CHARGE_PUBLISHED'), NotificationTarget.charges);
    });

    test('anything else has nowhere to go', () {
      expect(target('something_new'), NotificationTarget.none);
      expect(notificationTarget(const {}), NotificationTarget.none);
    });
  });

  group('NotificationRouter', () {
    late GoRouter router;
    late HomeTabBloc tabs;
    late NotificationRouter notifications;

    setUp(() {
      router = GoRouter(
        initialLocation: '/notifications',
        routes: [
          GoRoute(path: '/home', builder: (_, __) => const Text('home')),
          GoRoute(path: '/notifications', builder: (_, __) => const Text('notifications')),
          GoRoute(path: '/payment-history', builder: (_, __) => const Text('history')),
        ],
      );
      tabs = HomeTabBloc();
      notifications = NotificationRouter(router: router, homeTabs: tabs);
    });

    tearDown(() => tabs.close());

    testWidgets('a pass decision switches to the passes tab on the home screen', (tester) async {
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      expect(notifications.open({'type': 'pass_decided'}), isTrue);
      await tester.pumpAndSettle();

      expect(tabs.state, const HomeTabState(HomeTabs.passes));
      expect(find.text('home'), findsOneWidget);
    });

    testWidgets('a payment opens the history screen', (tester) async {
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      expect(notifications.open({'type': 'payment_success'}), isTrue);
      await tester.pumpAndSettle();

      expect(find.text('history'), findsOneWidget);
    });

    testWidgets('an unknown notification changes nothing', (tester) async {
      await tester.pumpWidget(MaterialApp.router(routerConfig: router));
      expect(notifications.open({'type': 'mystery'}), isFalse);
      await tester.pumpAndSettle();

      expect(tabs.state, const HomeTabState(HomeTabs.charges));
      expect(find.text('notifications'), findsOneWidget);
    });
  });
}
