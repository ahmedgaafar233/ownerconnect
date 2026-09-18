import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart' as fb;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:google_sign_in/google_sign_in.dart';
import '../../../../core/constants/api_endpoints.dart';
import 'auth_repository.dart';

class FirebaseAuthRepository implements AuthRepository {
  final fb.FirebaseAuth? _injectedFirebaseAuth;
  final Dio _dio;
  final FlutterSecureStorage _storage;

  /// Cached between a Google/Email sign-in that returned `link_required` and
  /// the follow-up [linkAccount] call — the phone+code submission must reuse
  /// the exact same Firebase ID token, not a fresh one.
  String? _pendingLinkIdToken;

  FirebaseAuthRepository({
    fb.FirebaseAuth? firebaseAuth,
    required Dio dio,
    FlutterSecureStorage storage = const FlutterSecureStorage(),
  })  : _injectedFirebaseAuth = firebaseAuth,
        _dio = dio,
        _storage = storage;

  /// Resolved lazily (never in the constructor): `FirebaseAuth.instance`
  /// throws if no Firebase app has been initialized, which is expected
  /// whenever no Firebase project is configured yet. Real sign-in/OTP paths
  /// need it and will surface that error; the dev-bypass path and every
  /// other construction of this repository (tests included) must not.
  fb.FirebaseAuth get _firebaseAuth => _injectedFirebaseAuth ?? fb.FirebaseAuth.instance;

  /// Initiate Phone Verification with Firebase Auth.
  /// Callbacks trigger codeSent, verificationCompleted, or verificationFailed.
  @override
  Future<void> verifyPhoneNumber({
    required String phoneNumber,
    required Function(String verificationId, int? resendToken) onCodeSent,
    required Function(fb.PhoneAuthCredential credential) onVerificationCompleted,
    required Function(fb.FirebaseAuthException error) onVerificationFailed,
    required Function(String verificationId) onCodeAutoRetrievalTimeout,
  }) async {
    await _firebaseAuth.verifyPhoneNumber(
      phoneNumber: phoneNumber,
      verificationCompleted: (fb.PhoneAuthCredential credential) async {
        onVerificationCompleted(credential);
      },
      verificationFailed: onVerificationFailed,
      codeSent: onCodeSent,
      codeAutoRetrievalTimeout: onCodeAutoRetrievalTimeout,
      timeout: const Duration(seconds: 60),
    );
  }

  /// Complete sign-in using SMS code entered by the user.
  /// Obtains the Firebase ID Token and sends it to the Django backend.
  @override
  Future<Map<String, dynamic>> signInWithSmsCode({
    required String verificationId,
    required String smsCode,
  }) async {
    final credential = fb.PhoneAuthProvider.credential(
      verificationId: verificationId,
      smsCode: smsCode,
    );

    final userCredential = await _firebaseAuth.signInWithCredential(credential);
    final firebaseUser = userCredential.user;

    if (firebaseUser == null) {
      throw Exception('Firebase authentication failed: User is null.');
    }

    final idToken = await firebaseUser.getIdToken();
    if (idToken == null || idToken.isEmpty) {
      throw Exception('Failed to obtain Firebase ID token.');
    }

    return await _authenticateWithBackend(idToken);
  }

  /// Complete sign-in using an auto-completed PhoneAuthCredential.
  @override
  Future<Map<String, dynamic>> signInWithCredential(fb.PhoneAuthCredential credential) async {
    final userCredential = await _firebaseAuth.signInWithCredential(credential);
    final firebaseUser = userCredential.user;

    if (firebaseUser == null) {
      throw Exception('Firebase authentication failed: User is null.');
    }

    final idToken = await firebaseUser.getIdToken();
    if (idToken == null || idToken.isEmpty) {
      throw Exception('Failed to obtain Firebase ID token.');
    }

    return await _authenticateWithBackend(idToken);
  }

  /// Debug-only shortcut that skips the real Firebase SMS flow entirely and
  /// authenticates straight against the backend's ALLOW_DEV_AUTH_BYPASS path
  /// (see users/views.py FirebaseAuthView). Works with zero Firebase project
  /// configuration, since it never touches the Firebase SDK. The caller is
  /// responsible for only exposing this behind a kDebugMode-gated UI control.
  @override
  Future<Map<String, dynamic>> signInWithDevBypass(String phone) {
    return _authenticateWithBackend('dev_test_token_$phone');
  }

  @override
  Future<Map<String, dynamic>> signInWithGoogle() async {
    final account = await GoogleSignIn.instance.authenticate();
    final googleIdToken = account.authentication.idToken;
    if (googleIdToken == null) {
      throw Exception('Google sign-in did not return an ID token.');
    }

    final credential = fb.GoogleAuthProvider.credential(idToken: googleIdToken);
    final userCredential = await _firebaseAuth.signInWithCredential(credential);
    final idToken = await userCredential.user?.getIdToken();
    if (idToken == null || idToken.isEmpty) {
      throw Exception('Failed to obtain Firebase ID token.');
    }

    return _authenticateWithBackend(idToken);
  }

  @override
  Future<Map<String, dynamic>> signInWithEmail({required String email, required String password}) async {
    final userCredential = await _firebaseAuth.signInWithEmailAndPassword(email: email, password: password);
    final idToken = await userCredential.user?.getIdToken();
    if (idToken == null || idToken.isEmpty) {
      throw Exception('Failed to obtain Firebase ID token.');
    }
    return _authenticateWithBackend(idToken);
  }

  @override
  Future<Map<String, dynamic>> registerWithEmail({required String email, required String password}) async {
    final userCredential = await _firebaseAuth.createUserWithEmailAndPassword(email: email, password: password);
    final idToken = await userCredential.user?.getIdToken();
    if (idToken == null || idToken.isEmpty) {
      throw Exception('Failed to obtain Firebase ID token.');
    }
    return _authenticateWithBackend(idToken);
  }

  @override
  Future<Map<String, dynamic>> linkAccount({required String phone, required String code}) async {
    final idToken = _pendingLinkIdToken;
    if (idToken == null) {
      throw Exception('No pending sign-in to link — please sign in again.');
    }
    return _authenticateWithBackend(idToken, phone: phone, code: code);
  }

  /// Fetches the authenticated user's profile from /api/me/ and persists the
  /// resolved resort so every subsequent request is locked to it (see
  /// TenantInterceptor). Returns the raw profile map.
  ///
  /// Must be called right after a successful sign-in (and on app start, to
  /// re-validate a stored session) — this is what turns "has a JWT" into
  /// "knows which village they belong to".
  @override
  Future<Map<String, dynamic>> fetchAndPersistProfile() async {
    final response = await _dio.get(ApiEndpoints.me);
    final profile = response.data as Map<String, dynamic>;

    final resortId = profile['resort'];
    final resortName = profile['resort_name'] as String?;

    if (resortId != null) {
      await _storage.write(key: 'active_resort_id', value: resortId.toString());
      if (resortName != null) {
        await _storage.write(key: 'resort_name', value: resortName);
      }
    } else {
      // No resort linked yet — make sure no stale value from a previous
      // session lingers and gets sent as X-Resort-ID.
      await _storage.delete(key: 'active_resort_id');
      await _storage.delete(key: 'resort_name');
    }

    return profile;
  }

  @override
  Future<Map<String, dynamic>> updateFullname(String fullname) async {
    final response = await _dio.patch(ApiEndpoints.me, data: {'fullname': fullname});
    return response.data as Map<String, dynamic>;
  }

  /// Whether a stored access token exists. A quick local check used by the
  /// splash screen before deciding whether to call fetchAndPersistProfile.
  @override
  Future<bool> isLoggedIn() async {
    final token = await _storage.read(key: 'access_token');
    return token != null && token.isNotEmpty;
  }

  /// Sends the Firebase ID Token to Django backend and saves the returned JWT
  /// — unless the backend responds with `link_required` (a first-time
  /// Google/Email sign-in that isn't linked to any owner yet), in which case
  /// no tokens exist yet and the id_token is cached for [linkAccount].
  Future<Map<String, dynamic>> _authenticateWithBackend(
    String idToken, {
    String? phone,
    String? code,
  }) async {
    final body = <String, dynamic>{'id_token': idToken};
    if (phone != null) body['phone'] = phone;
    if (code != null) body['code'] = code;

    final response = await _dio.post(ApiEndpoints.firebaseAuth, data: body);

    if (response.statusCode != 200 && response.statusCode != 201) {
      throw Exception('Backend authentication failed: ${response.statusMessage}');
    }

    final data = response.data as Map<String, dynamic>;

    if (data['link_required'] == true) {
      _pendingLinkIdToken = idToken;
      return data;
    }

    final accessToken = data['access'] as String;
    final refreshToken = data['refresh'] as String;

    await _storage.write(key: 'access_token', value: accessToken);
    await _storage.write(key: 'refresh_token', value: refreshToken);
    _pendingLinkIdToken = null;

    return data;
  }

  /// Sign out from Firebase and clear local JWTs. A session started via the
  /// dev bypass never touched Firebase, and Firebase may not even be
  /// configured yet — either way, clearing local storage is the part that
  /// actually matters, so it must not be skipped if the Firebase call fails.
  @override
  Future<void> signOut() async {
    try {
      await _firebaseAuth.signOut();
    } catch (_) {}
    await _storage.deleteAll();
  }
}
