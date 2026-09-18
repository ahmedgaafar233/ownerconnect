import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../bloc/support_bloc.dart';
import '../bloc/support_event.dart';
import '../bloc/support_state.dart';
import '../widgets/ticket_card.dart';

class SupportTicketsScreen extends StatefulWidget {
  const SupportTicketsScreen({Key? key}) : super(key: key);

  @override
  State<SupportTicketsScreen> createState() => _SupportTicketsScreenState();
}

class _SupportTicketsScreenState extends State<SupportTicketsScreen> {
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    context.read<SupportBloc>().add(const FetchTicketsEvent(page: 1));
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
      final state = context.read<SupportBloc>().state;
      if (state is TicketsLoadedState && !state.hasReachedMax && !state.isFetchingMore) {
        context.read<SupportBloc>().add(FetchTicketsEvent(page: state.currentPage + 1));
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
        title: Text(loc.translate('tickets_title')),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          // Open Ticket creation sheet/dialog
        },
        backgroundColor: AppColors.secondary,
        icon: const Icon(Icons.add),
        label: Text(loc.translate('create_ticket')),
      ),
      body: BlocBuilder<SupportBloc, SupportState>(
        builder: (context, state) {
          if (state is SupportLoadingState) {
            return const Center(child: CircularProgressIndicator());
          } else if (state is TicketsLoadedState) {
            if (state.tickets.isEmpty) {
              return Center(child: Text(loc.translate('no_tickets')));
            }
            return ListView.builder(
              controller: _scrollController,
              itemCount: state.hasReachedMax
                  ? state.tickets.length
                  : state.tickets.length + 1,
              itemBuilder: (context, index) {
                if (index >= state.tickets.length) {
                  return const Padding(
                    padding: EdgeInsets.all(16.0),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                return TicketCard(ticket: state.tickets[index]);
              },
            );
          } else if (state is SupportErrorState) {
            return Center(child: Text(state.message));
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}
