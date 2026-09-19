import 'package:equatable/equatable.dart';
import '../../data/models/notification_model.dart';

abstract class NotificationState extends Equatable {
  final int unreadCount;

  const NotificationState({this.unreadCount = 0});

  @override
  List<Object?> get props => [unreadCount];
}

class NotificationInitialState extends NotificationState {
  const NotificationInitialState({super.unreadCount});
}

class NotificationLoadingState extends NotificationState {
  const NotificationLoadingState({super.unreadCount});
}

class NotificationsLoadedState extends NotificationState {
  final List<NotificationModel> notifications;
  final bool hasReachedMax;
  final int currentPage;
  final bool isFetchingMore;

  const NotificationsLoadedState({
    required this.notifications,
    required this.hasReachedMax,
    this.currentPage = 1,
    this.isFetchingMore = false,
    super.unreadCount,
  });

  NotificationsLoadedState copyWith({
    List<NotificationModel>? notifications,
    bool? hasReachedMax,
    int? currentPage,
    bool? isFetchingMore,
    int? unreadCount,
  }) {
    return NotificationsLoadedState(
      notifications: notifications ?? this.notifications,
      hasReachedMax: hasReachedMax ?? this.hasReachedMax,
      currentPage: currentPage ?? this.currentPage,
      isFetchingMore: isFetchingMore ?? this.isFetchingMore,
      unreadCount: unreadCount ?? this.unreadCount,
    );
  }

  @override
  List<Object?> get props => [notifications, hasReachedMax, currentPage, isFetchingMore, unreadCount];
}

class NotificationErrorState extends NotificationState {
  final String message;

  const NotificationErrorState({required this.message, super.unreadCount});

  @override
  List<Object?> get props => [message, unreadCount];
}
