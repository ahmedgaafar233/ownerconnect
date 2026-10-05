import 'package:flutter/foundation.dart';

/// Holds the router on the splash screen until the splash has been on screen
/// long enough to actually be seen. Without it the auth check finishes in a
/// blink and the router jumps straight past, so the animated OWC mark never
/// got to draw itself.
class SplashGate extends ChangeNotifier {
  SplashGate() : _done = false;

  /// A gate that never holds anything back — for tests, and any caller that
  /// doesn't show a splash.
  SplashGate.open() : _done = true;

  bool _done;

  bool get isDone => _done;

  void complete() {
    if (_done) return;
    _done = true;
    notifyListeners();
  }
}
