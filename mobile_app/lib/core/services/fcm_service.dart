import 'package:dio/dio.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import 'notification_presenter.dart';

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

  final NotificationPresenter _presenter = NotificationPresenter();

  /// Called with a push's data payload when the person taps a notification —
  /// whether it was drawn by Firebase (app closed/background) or by us (app
  /// open) — so the app can take them to the thing it's about.
  void Function(Map<String, dynamic> data)? onNotificationTap;

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

    // The channel (sound + pop-up) must exist before any push targets it.
    _presenter.onTap = (data) => onNotificationTap?.call(data);
    await _presenter.initialize();
    await _messaging.setForegroundNotificationPresentationOptions(alert: true, badge: true, sound: true);

    // 3. Handle Foreground Messages — Firebase draws nothing while the app is
    // open, so show it ourselves (sound + pop-up) and let the app refresh.
    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      if (kDebugMode) {
        print('Foreground notification received: ${message.notification?.title}');
      }
      _presenter.show(message);
      onForegroundMessage?.call(message);
    });

    // Tapped while the app was in the background...
    FirebaseMessaging.onMessageOpenedApp.listen((message) => onNotificationTap?.call(message.data));
    // ...or launched from a tap while it was closed.
    final initial = await _messaging.getInitialMessage();
    if (initial != null) onNotificationTap?.call(initial.data);

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
