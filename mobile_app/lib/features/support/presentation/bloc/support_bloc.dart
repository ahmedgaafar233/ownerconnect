import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/api_error.dart';
import '../../data/repositories/support_repository.dart';
import 'support_event.dart';
import 'support_state.dart';

class SupportBloc extends Bloc<SupportEvent, SupportState> {
  final SupportRepository repository;

  SupportBloc({required this.repository}) : super(SupportInitialState()) {
    on<FetchTicketsEvent>(_onFetchTickets);
    on<CreateTicketEvent>(_onCreateTicket);
  }

  Future<void> _onFetchTickets(FetchTicketsEvent event, Emitter<SupportState> emit) async {
    final currentState = state;

    if (event.page == 1) {
      emit(SupportLoadingState());
      try {
        final tickets = await repository.getTickets(
          page: 1,
          category: event.category,
          excludeCategory: event.excludeCategory,
          status: event.status,
        );
        emit(TicketsLoadedState(
          tickets: tickets,
          hasReachedMax: tickets.length < 15,
          currentPage: 1,
          isFetchingMore: false,
        ));
      } catch (e) {
        emit(SupportErrorState(message: e.toString()));
      }
    } else if (currentState is TicketsLoadedState && !currentState.hasReachedMax && !currentState.isFetchingMore) {
      emit(currentState.copyWith(isFetchingMore: true));
      try {
        final newTickets = await repository.getTickets(
          page: event.page,
          category: event.category,
          excludeCategory: event.excludeCategory,
          status: event.status,
        );
        if (newTickets.isEmpty) {
          emit(currentState.copyWith(hasReachedMax: true, isFetchingMore: false));
        } else {
          emit(TicketsLoadedState(
            tickets: List.from(currentState.tickets)..addAll(newTickets),
            hasReachedMax: newTickets.length < 15,
            currentPage: event.page,
            isFetchingMore: false,
          ));
        }
      } catch (e) {
        emit(currentState.copyWith(isFetchingMore: false));
      }
    }
  }

  Future<void> _onCreateTicket(CreateTicketEvent event, Emitter<SupportState> emit) async {
    emit(SupportLoadingState());
    try {
      final ticket = await repository.createTicket(
        unitId: event.unitId,
        category: event.category,
        serviceType: event.serviceType,
        priority: event.priority,
        subject: event.subject,
        description: event.description,
      );
      emit(TicketCreatedState(ticket: ticket));
    } catch (e) {
      emit(SupportErrorState(message: apiErrorMessage(e)));
    }
  }
}
