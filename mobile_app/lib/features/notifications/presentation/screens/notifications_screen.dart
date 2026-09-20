import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../data/models/notification_model.dart';
import '../bloc/notification_bloc.dart';
import '../bloc/notification_event.dart';
import '../bloc/notification_state.dart';
import '../../../../core/widgets/app_loading_indicator.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({Key? key}) : super(key: key);

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    context.read<NotificationBloc>().add(const FetchNotificationsEvent(page: 1));
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_isBottom) {
      final state = context.read<NotificationBloc>().state;
      if (state is NotificationsLoadedState && !state.hasReachedMax && !state.isFetchingMore) {
        context.read<NotificationBloc>().add(FetchNotificationsEvent(page: state.currentPage + 1));
      }
    }
  }

  bool get _isBottom {
    if (!_scrollController.hasClients) return false;
    final maxScroll = _scrollController.position.maxScrollExtent;
    final currentScroll = _scrollController.offset;
    return currentScroll >= (maxScroll * 0.9);
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.translate('notifications_title')),
        actions: [
          TextButton(
            onPressed: () => context.read<NotificationBloc>().add(const MarkAllReadEvent()),
            child: Text(
              loc.translate('mark_all_read'),
              style: const TextStyle(color: Colors.white),
            ),
          ),
        ],
      ),
      body: BlocBuilder<NotificationBloc, NotificationState>(
        builder: (context, state) {
          if (state is NotificationLoadingState) {
            return const Center(child: AppLoadingIndicator());
          } else if (state is NotificationsLoadedState) {
            if (state.notifications.isEmpty) {
              return Center(child: Text(loc.translate('no_notifications_yet')));
            }
            return RefreshIndicator(
              onRefresh: () async {
                context.read<NotificationBloc>().add(const FetchNotificationsEvent(page: 1));
              },
              child: ListView.builder(
                controller: _scrollController,
                itemCount: state.hasReachedMax ? state.notifications.length : state.notifications.length + 1,
                itemBuilder: (context, index) {
                  if (index >= state.notifications.length) {
                    return const Padding(
                      padding: EdgeInsets.all(16.0),
                      child: Center(child: AppLoadingIndicator()),
                    );
                  }
                  final notification = state.notifications[index];
                  return _NotificationTile(
                    notification: notification,
                    onTap: () => context.read<NotificationBloc>().add(MarkReadEvent(id: notification.id)),
                  );
                },
              ),
            );
          } else if (state is NotificationErrorState) {
            return Center(child: Text(state.message));
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  final NotificationModel notification;
  final VoidCallback onTap;

  const _NotificationTile({required this.notification, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      color: notification.isRead ? AppColors.cardBg : AppColors.primary.withOpacity(0.04),
      child: ListTile(
        onTap: onTap,
        contentPadding: const EdgeInsets.all(16),
        leading: CircleAvatar(
          backgroundColor: notification.isRead ? AppColors.border : AppColors.secondary.withOpacity(0.15),
          child: Icon(
            Icons.notifications,
            color: notification.isRead ? AppColors.textSecondary : AppColors.secondary,
            size: 20,
          ),
        ),
        title: Text(
          notification.title,
          style: TextStyle(
            fontSize: 15,
            fontWeight: notification.isRead ? FontWeight.w500 : FontWeight.bold,
            color: AppColors.textPrimary,
          ),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 4),
          child: Text(
            notification.body,
            style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
          ),
        ),
        trailing: notification.isRead
            ? null
            : Container(
                width: 10,
                height: 10,
                decoration: const BoxDecoration(color: AppColors.secondary, shape: BoxShape.circle),
              ),
      ),
    );
  }
}
