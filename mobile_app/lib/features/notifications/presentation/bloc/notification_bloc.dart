import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/models/notification_model.dart';
import '../../data/repositories/notification_repository.dart';
import 'notification_event.dart';
import 'notification_state.dart';

class NotificationBloc extends Bloc<NotificationEvent, NotificationState> {
  final NotificationRepository repository;

  NotificationBloc({required this.repository}) : super(const NotificationInitialState()) {
    on<FetchNotificationsEvent>(_onFetchNotifications);
    on<FetchUnreadCountEvent>(_onFetchUnreadCount);
    on<MarkReadEvent>(_onMarkRead);
    on<MarkAllReadEvent>(_onMarkAllRead);
  }

  Future<void> _onFetchNotifications(FetchNotificationsEvent event, Emitter<NotificationState> emit) async {
    final currentState = state;

    if (event.page == 1) {
      emit(NotificationLoadingState(unreadCount: currentState.unreadCount));
      try {
        final notifications = await repository.getNotifications(page: 1);
        emit(NotificationsLoadedState(
          notifications: notifications,
          hasReachedMax: notifications.length < 20,
          currentPage: 1,
          isFetchingMore: false,
          unreadCount: currentState.unreadCount,
        ));
      } catch (e) {
        emit(NotificationErrorState(message: e.toString(), unreadCount: currentState.unreadCount));
      }
    } else if (currentState is NotificationsLoadedState && !currentState.hasReachedMax && !currentState.isFetchingMore) {
      emit(currentState.copyWith(isFetchingMore: true));
      try {
        final newNotifications = await repository.getNotifications(page: event.page);
        if (newNotifications.isEmpty) {
          emit(currentState.copyWith(hasReachedMax: true, isFetchingMore: false));
        } else {
          emit(NotificationsLoadedState(
            notifications: List<NotificationModel>.from(currentState.notifications)..addAll(newNotifications),
            hasReachedMax: newNotifications.length < 20,
            currentPage: event.page,
            isFetchingMore: false,
            unreadCount: currentState.unreadCount,
          ));
        }
      } catch (e) {
        emit(currentState.copyWith(isFetchingMore: false));
      }
    }
  }

  Future<void> _onFetchUnreadCount(FetchUnreadCountEvent event, Emitter<NotificationState> emit) async {
    try {
      final count = await repository.getUnreadCount();
      final current = state;
      if (current is NotificationsLoadedState) {
        emit(current.copyWith(unreadCount: count));
      } else if (current is NotificationErrorState) {
        emit(NotificationErrorState(message: current.message, unreadCount: count));
      } else if (current is NotificationLoadingState) {
        emit(NotificationLoadingState(unreadCount: count));
      } else {
        emit(NotificationInitialState(unreadCount: count));
      }
    } catch (_) {
      // Best-effort badge refresh — silently ignore, next attempt will retry.
    }
  }

  Future<void> _onMarkRead(MarkReadEvent event, Emitter<NotificationState> emit) async {
    final current = state;
    if (current is! NotificationsLoadedState) return;
    final idx = current.notifications.indexWhere((n) => n.id == event.id);
    if (idx == -1 || current.notifications[idx].isRead) return;

    try {
      await repository.markRead(event.id);
      final updated = List<NotificationModel>.from(current.notifications);
      updated[idx] = updated[idx].copyWith(isRead: true);
      emit(current.copyWith(
        notifications: updated,
        unreadCount: current.unreadCount > 0 ? current.unreadCount - 1 : 0,
      ));
    } catch (_) {
      // Leave state unchanged — user can retry the tap.
    }
  }

  Future<void> _onMarkAllRead(MarkAllReadEvent event, Emitter<NotificationState> emit) async {
    final current = state;
    try {
      await repository.markAllRead();
      if (current is NotificationsLoadedState) {
        final updated = current.notifications.map((n) => n.copyWith(isRead: true)).toList();
        emit(current.copyWith(notifications: updated, unreadCount: 0));
      } else {
        emit(const NotificationInitialState(unreadCount: 0));
      }
    } catch (_) {
      // Best-effort — leave state unchanged on failure.
    }
  }
}
