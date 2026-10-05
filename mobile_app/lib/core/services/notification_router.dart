import 'package:go_router/go_router.dart';

import '../../features/home/presentation/bloc/home_tab_bloc.dart';
import '../../features/home/presentation/bloc/home_tab_event.dart';
import '../../features/home/presentation/bloc/home_tab_state.dart';

/// Where tapping a notification should take the person.
enum NotificationTarget { charges, support, passes, paymentHistory, none }

/// Maps a notification to its destination. [data] is the payload the backend
/// sends with every push/inbox row (`data.type`, snake_case); [type] is the
/// inbox row's own enum (`CHARGE_PUBLISHED`, ...), used when the payload
/// carries no type of its own.
NotificationTarget notificationTarget(Map<String, dynamic> data, {String type = ''}) {
  switch ((data['type'] as String? ?? type).toLowerCase()) {
    case 'charges_published':
    case 'charge_published':
    case 'payment_deferred':
    case 'unit_payment_deferred':
    case 'payment_plan_decided':
      return NotificationTarget.charges;
    case 'payment_success':
    case 'unit_payment_success':
      return NotificationTarget.paymentHistory;
    case 'ticket_reply':
    case 'ticket_status':
      return NotificationTarget.support;
    case 'pass_decided':
      return NotificationTarget.passes;
    default:
      return NotificationTarget.none;
  }
}

/// Opens the screen a notification is about. Lives at app level (built from
/// the router and tab bloc the app already owns), so it works the same from
/// the in-app list and from a tap on a system notification.
class NotificationRouter {
  NotificationRouter({required GoRouter router, required HomeTabBloc homeTabs})
      : _router = router,
        _homeTabs = homeTabs;

  final GoRouter _router;
  final HomeTabBloc _homeTabs;

  /// Returns whether the notification had somewhere to go.
  bool open(Map<String, dynamic> data, {String type = ''}) {
    final target = notificationTarget(data, type: type);
    switch (target) {
      case NotificationTarget.charges:
        return _showTab(HomeTabs.charges);
      case NotificationTarget.support:
        return _showTab(HomeTabs.support);
      case NotificationTarget.passes:
        return _showTab(HomeTabs.passes);
      case NotificationTarget.paymentHistory:
        _router.push('/payment-history');
        return true;
      case NotificationTarget.none:
        return false;
    }
  }

  bool _showTab(int index) {
    _homeTabs.add(HomeTabSelected(index));
    _router.go('/home');
    return true;
  }
}
