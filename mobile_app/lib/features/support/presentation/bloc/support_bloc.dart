import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/repositories/support_repository.dart';
import 'support_event.dart';
import 'support_state.dart';

class SupportBloc extends Bloc<SupportEvent, SupportState> {
  final SupportRepository repository;

  SupportBloc({required this.repository}) : super(SupportInitialState()) {
    on<FetchTicketsEvent>(_onFetchTickets);
    on<CreateTicketEvent>(_onCreateTicket);
    on<FetchVisitorPassesEvent>(_onFetchVisitorPasses);
    on<CreateVisitorPassEvent>(_onCreateVisitorPass);
  }

  Future<void> _onFetchTickets(FetchTicketsEvent event, Emitter<SupportState> emit) async {
    final currentState = state;

    if (event.page == 1) {
      emit(SupportLoadingState());
      try {
        final tickets = await repository.getTickets(
          page: 1,
          category: event.category,
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
        priority: event.priority,
        subject: event.subject,
        description: event.description,
      );
      emit(TicketCreatedState(ticket: ticket));
    } catch (e) {
      emit(SupportErrorState(message: e.toString()));
    }
  }

  Future<void> _onFetchVisitorPasses(FetchVisitorPassesEvent event, Emitter<SupportState> emit) async {
    if (event.page == 1) emit(SupportLoadingState());
    try {
      final passes = await repository.getVisitorPasses(page: event.page);
      emit(VisitorPassesLoadedState(passes: passes));
    } catch (e) {
      emit(SupportErrorState(message: e.toString()));
    }
  }

  Future<void> _onCreateVisitorPass(CreateVisitorPassEvent event, Emitter<SupportState> emit) async {
    emit(SupportLoadingState());
    try {
      final pass = await repository.createVisitorPass(
        unitId: event.unitId,
        passType: event.passType,
        visitorName: event.visitorName,
        nationalId: event.nationalId,
        carPlate: event.carPlate,
        validFrom: event.validFrom,
        validTo: event.validTo,
      );
      emit(VisitorPassCreatedState(pass: pass));
    } catch (e) {
      emit(SupportErrorState(message: e.toString()));
    }
  }
}
