import 'package:dio/dio.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  if (kDebugMode) {
    print('Handling background message: ${message.messageId}');
  }
}

class FcmService {
  final FirebaseMessaging _messaging = FirebaseMessaging.instance;
  final Dio _dio;

  /// Invoked on every foreground push so the caller can refresh e.g. the
  /// notifications bell badge while the app is open. Mutable rather than a
  /// constructor param: this service is built once in AppDependencies
  /// (bootstrap, before the widget tree — and therefore before
  /// NotificationBloc — exists), so the owning widget assigns this once
  /// it's created its own bloc instance.
  void Function(RemoteMessage message)? onForegroundMessage;

  FcmService(this._dio);

  /// Initializes FCM permissions, handlers, and token registration.
  Future<void> initialize() async {
    // 1. Request Notification Permissions
    final settings = await _messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      provisional: false,
    );

    if (settings.authorizationStatus == AuthorizationStatus.authorized) {
      if (kDebugMode) {
        print('User granted notification permissions');
      }
    }

    // 2. Set Background Message Handler
    FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

    // 3. Handle Foreground Messages
    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      if (kDebugMode) {
        print('Foreground notification received: ${message.notification?.title}');
      }
      onForegroundMessage?.call(message);
    });

    // 4. Token Refresh Listener
    _messaging.onTokenRefresh.listen((newToken) {
      registerDeviceToken(newToken);
    });
  }

  /// Fetches the current FCM token and registers it with the Django backend.
  Future<void> registerCurrentToken() async {
    try {
      final token = await _messaging.getToken();
      if (token != null && token.isNotEmpty) {
        await registerDeviceToken(token);
      }
    } catch (e) {
      if (kDebugMode) {
        print('Error fetching FCM token: $e');
      }
    }
  }

  /// Sends the device FCM token to Django `/api/auth/fcm-token/`.
  Future<void> registerDeviceToken(String fcmToken) async {
    try {
      final response = await _dio.post(
        '/api/auth/fcm-token/',
        data: {
          'fcm_token': fcmToken,
          'os': defaultTargetPlatform.name,
        },
      );
      if (kDebugMode) {
        print('FCM token registered with backend: ${response.statusCode}');
      }
    } catch (e) {
      if (kDebugMode) {
        print('Failed to register FCM token with backend: $e');
      }
    }
  }
}
