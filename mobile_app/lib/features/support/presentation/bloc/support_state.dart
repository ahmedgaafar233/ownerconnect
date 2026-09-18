import 'package:equatable/equatable.dart';
import '../../data/models/ticket_model.dart';
import '../../data/models/visitor_pass_model.dart';

abstract class SupportState extends Equatable {
  const SupportState();

  @override
  List<Object?> get props => [];
}

class SupportInitialState extends SupportState {}

class SupportLoadingState extends SupportState {}

class TicketsLoadedState extends SupportState {
  final List<TicketModel> tickets;
  final bool hasReachedMax;
  final int currentPage;
  final bool isFetchingMore;

  const TicketsLoadedState({
    required this.tickets,
    required this.hasReachedMax,
    this.currentPage = 1,
    this.isFetchingMore = false,
  });

  TicketsLoadedState copyWith({
    List<TicketModel>? tickets,
    bool? hasReachedMax,
    int? currentPage,
    bool? isFetchingMore,
  }) {
    return TicketsLoadedState(
      tickets: tickets ?? this.tickets,
      hasReachedMax: hasReachedMax ?? this.hasReachedMax,
      currentPage: currentPage ?? this.currentPage,
      isFetchingMore: isFetchingMore ?? this.isFetchingMore,
    );
  }

  @override
  List<Object?> get props => [tickets, hasReachedMax, currentPage, isFetchingMore];
}

class TicketCreatedState extends SupportState {
  final TicketModel ticket;

  const TicketCreatedState({required this.ticket});

  @override
  List<Object?> get props => [ticket];
}

class VisitorPassesLoadedState extends SupportState {
  final List<VisitorPassModel> passes;

  const VisitorPassesLoadedState({required this.passes});

  @override
  List<Object?> get props => [passes];
}

class VisitorPassCreatedState extends SupportState {
  final VisitorPassModel pass;

  const VisitorPassCreatedState({required this.pass});

  @override
  List<Object?> get props => [pass];
}

class SupportErrorState extends SupportState {
  final String message;

  const SupportErrorState({required this.message});

  @override
  List<Object?> get props => [message];
}
