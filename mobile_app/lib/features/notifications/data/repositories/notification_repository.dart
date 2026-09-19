import 'package:dio/dio.dart';
import '../../../../core/constants/api_endpoints.dart';
import '../models/notification_model.dart';

class NotificationRepository {
  final Dio dio;

  NotificationRepository({required this.dio});

  Future<List<NotificationModel>> getNotifications({int page = 1}) async {
    final response = await dio.get(ApiEndpoints.notifications, queryParameters: {'page': page});
    final results = response.data['results'] as List;
    return results.map((e) => NotificationModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> markRead(int id) async {
    await dio.post(ApiEndpoints.notificationRead(id));
  }

  Future<void> markAllRead() async {
    await dio.post(ApiEndpoints.notificationsMarkAllRead);
  }

  Future<int> getUnreadCount() async {
    final response = await dio.get(ApiEndpoints.notificationsUnreadCount);
    return response.data['count'] as int? ?? 0;
  }
}
