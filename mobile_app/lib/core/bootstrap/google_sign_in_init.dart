import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:google_sign_in/google_sign_in.dart';

/// Google Sign-In's one-time `initialize()` does a network round trip. It used
/// to be awaited before the first frame, which is most of why the launch
/// splash dragged on. It now runs in the background; anything that actually
/// starts a Google sign-in awaits [ready] first (the plugin requires
/// initialize to have finished before any other call).
class GoogleSignInInit {
  GoogleSignInInit._();

  static Future<void> ready = Future.value();

  /// Starts initialisation without waiting for it. Never throws.
  static void start() {
    ready = () async {
      try {
        // serverClientId is the "Web client (auto created by Google Service)"
        // OAuth client id — copy it from the re-downloaded google-services.json
        // (oauth_client entries with client_type 3).
        await GoogleSignIn.instance.initialize(serverClientId: dotenv.env['GOOGLE_SERVER_CLIENT_ID']);
      } catch (_) {
        // No Google client configured yet — the sign-in button surfaces its
        // own error when tapped rather than this blocking app startup.
      }
    }();
  }
}
