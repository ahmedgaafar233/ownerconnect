import 'package:equatable/equatable.dart';

abstract class NotificationEvent extends Equatable {
  const NotificationEvent();

  @override
  List<Object?> get props => [];
}

class FetchNotificationsEvent extends NotificationEvent {
  final int page;

  const FetchNotificationsEvent({this.page = 1});

  @override
  List<Object?> get props => [page];
}

class FetchUnreadCountEvent extends NotificationEvent {
  const FetchUnreadCountEvent();
}

class MarkReadEvent extends NotificationEvent {
  final int id;

  const MarkReadEvent({required this.id});

  @override
  List<Object?> get props => [id];
}

class MarkAllReadEvent extends NotificationEvent {
  const MarkAllReadEvent();
}
