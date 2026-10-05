import 'dart:convert';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Shows a push as a real on-screen notification — sound, pop-up banner —
/// even while the app is open (Firebase only draws one itself when the app is
/// closed or in the background), and reports a tap on it.
class NotificationPresenter {
  /// Must match the channel the backend names in every push (see
  /// core/tasks.py ANDROID_CHANNEL_ID) and the manifest's default channel.
  static const channelId = 'owc_alerts';
  static const _soundResource = 'owc_notify';

  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  int _nextId = 1;

  /// Called with the push's data payload when the person taps a notification
  /// this presenter showed.
  void Function(Map<String, dynamic> data)? onTap;

  Future<void> initialize() async {
    await _plugin.initialize(
      settings: const InitializationSettings(
        android: AndroidInitializationSettings('ic_stat_owc'),
        iOS: DarwinInitializationSettings(),
      ),
      onDidReceiveNotificationResponse: (response) {
        final payload = response.payload;
        if (payload == null || payload.isEmpty) return;
        try {
          onTap?.call((jsonDecode(payload) as Map).cast<String, dynamic>());
        } catch (_) {
          // A payload we didn't write — nothing to open.
        }
      },
    );

    // Importance.max is what makes Android pop the notification up over
    // whatever's on screen (a heads-up banner) rather than just add it to the
    // shade. Channel settings can't be changed after creation, so the id is
    // versioned by name if this ever needs to change.
    await _plugin
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(const AndroidNotificationChannel(
          channelId,
          'OwnerConnect alerts',
          description: 'Charges, payments, service requests and pass decisions',
          importance: Importance.max,
          playSound: true,
          sound: RawResourceAndroidNotificationSound(_soundResource),
          enableVibration: true,
        ));
  }

  Future<void> show(RemoteMessage message) async {
    final title = message.notification?.title ?? message.data['title'] as String?;
    final body = message.notification?.body ?? message.data['body'] as String?;
    if (title == null && body == null) return;

    try {
      await _plugin.show(
        id: _nextId++,
        title: title,
        body: body,
        payload: jsonEncode(message.data),
        notificationDetails: const NotificationDetails(
          android: AndroidNotificationDetails(
            channelId,
            'OwnerConnect alerts',
            channelDescription: 'Charges, payments, service requests and pass decisions',
            importance: Importance.max,
            priority: Priority.high,
            playSound: true,
            sound: RawResourceAndroidNotificationSound(_soundResource),
            enableVibration: true,
            icon: 'ic_stat_owc',
            ticker: 'OwnerConnect',
          ),
          iOS: DarwinNotificationDetails(presentAlert: true, presentSound: true, presentBadge: true),
        ),
      );
    } catch (e) {
      // Not guarded by kDebugMode: this is exactly the failure that was invisible
      // in release builds (stripped sound/icon resources).
      debugPrint('Could not show notification: $e');
    }
  }
}
