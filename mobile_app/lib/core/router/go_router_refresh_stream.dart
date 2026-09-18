import 'dart:async';

import 'package:flutter/foundation.dart';

/// Standard go_router adapter that turns a Stream (here: AuthBloc.stream)
/// into a Listenable, so GoRouter's `redirect` re-runs on every AuthBloc
/// state change instead of only on navigation events.
class GoRouterRefreshStream extends ChangeNotifier {
  GoRouterRefreshStream(Stream<dynamic> stream) {
    notifyListeners();
    _subscription = stream.asBroadcastStream().listen((_) => notifyListeners());
  }

  late final StreamSubscription<dynamic> _subscription;

  @override
  void dispose() {
    _subscription.cancel();
    super.dispose();
  }
}
