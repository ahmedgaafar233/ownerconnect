import 'package:firebase_auth/firebase_auth.dart' as fb;

/// What AuthBloc actually depends on. Keeping this as an interface (rather
/// than the concrete FirebaseAuthRepository) means the bloc — and anything
/// that tests it — never has to touch the real Firebase SDK or secure
/// storage plugin.
abstract class AuthRepository {
  Future<void> verifyPhoneNumber({
    required String phoneNumber,
    required Function(String verificationId, int? resendToken) onCodeSent,
    required Function(fb.PhoneAuthCredential credential) onVerificationCompleted,
    required Function(fb.FirebaseAuthException error) onVerificationFailed,
    required Function(String verificationId) onCodeAutoRetrievalTimeout,
  });

  Future<Map<String, dynamic>> signInWithSmsCode({
    required String verificationId,
    required String smsCode,
  });

  Future<Map<String, dynamic>> signInWithCredential(fb.PhoneAuthCredential credential);

  Future<Map<String, dynamic>> signInWithDevBypass(String phone);

  /// Returns `{"link_required": true}` if this is the first sign-in for this
  /// Google identity (see FirebaseAuthView) — the caller must then collect
  /// phone+activation code and call [linkAccount]. Otherwise returns the
  /// normal token response.
  Future<Map<String, dynamic>> signInWithGoogle();

  Future<Map<String, dynamic>> signInWithEmail({required String email, required String password});

  Future<Map<String, dynamic>> registerWithEmail({required String email, required String password});

  /// Completes account linking for the Google/Email sign-in that most
  /// recently returned `link_required` — resubmits its cached id_token
  /// together with [phone] and the activation [code].
  Future<Map<String, dynamic>> linkAccount({required String phone, required String code});

  Future<Map<String, dynamic>> fetchAndPersistProfile();

  Future<Map<String, dynamic>> updateFullname(String fullname);

  Future<bool> isLoggedIn();

  Future<void> signOut();
}
