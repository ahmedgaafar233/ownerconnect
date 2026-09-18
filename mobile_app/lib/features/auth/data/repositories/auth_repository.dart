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

  Future<Map<String, dynamic>> fetchAndPersistProfile();

  Future<bool> isLoggedIn();

  Future<void> signOut();
}
