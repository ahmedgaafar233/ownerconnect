import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/repositories/financial_repository.dart';
import 'financial_event.dart';
import 'financial_state.dart';

class FinancialBloc extends Bloc<FinancialEvent, FinancialState> {
  final FinancialRepository repository;

  FinancialBloc({required this.repository}) : super(FinancialInitialState()) {
    on<FetchChargesEvent>(_onFetchCharges);
    on<InitiatePaymentEvent>(_onInitiatePayment);
    on<PaymentCompletedEvent>(_onPaymentCompleted);
    on<PaymentFailedEvent>(_onPaymentFailed);
  }

  Future<void> _onFetchCharges(
    FetchChargesEvent event,
    Emitter<FinancialState> emit,
  ) async {
    final currentState = state;

    if (event.page == 1) {
      emit(FinancialLoadingState());
      try {
        final charges = await repository.getCharges(
          page: 1,
          type: event.typeFilter,
          unpaidOnly: event.unpaidOnly,
        );
        emit(ChargesLoadedState(
          charges: charges,
          hasReachedMax: charges.length < 15,
          currentPage: 1,
          isFetchingMore: false,
        ));
      } catch (e) {
        emit(FinancialErrorState(errorMessage: e.toString()));
      }
    } else if (currentState is ChargesLoadedState && !currentState.hasReachedMax && !currentState.isFetchingMore) {
      emit(currentState.copyWith(isFetchingMore: true));
      try {
        final newCharges = await repository.getCharges(
          page: event.page,
          type: event.typeFilter,
          unpaidOnly: event.unpaidOnly,
        );

        if (newCharges.isEmpty) {
          emit(currentState.copyWith(hasReachedMax: true, isFetchingMore: false));
        } else {
          emit(ChargesLoadedState(
            charges: List.from(currentState.charges)..addAll(newCharges),
            hasReachedMax: newCharges.length < 15,
            currentPage: event.page,
            isFetchingMore: false,
          ));
        }
      } catch (e) {
        emit(currentState.copyWith(isFetchingMore: false));
      }
    }
  }

  Future<void> _onInitiatePayment(
    InitiatePaymentEvent event,
    Emitter<FinancialState> emit,
  ) async {
    final currentState = state;
    emit(FinancialLoadingState());
    try {
      final session = await repository.initiateOnlinePayment(event.chargeIds);
      emit(PaymentInitiatedState(paymentSession: session));
    } catch (e) {
      emit(FinancialErrorState(errorMessage: e.toString()));
      if (currentState is ChargesLoadedState) {
        emit(currentState);
      }
    }
  }

  Future<void> _onPaymentCompleted(
    PaymentCompletedEvent event,
    Emitter<FinancialState> emit,
  ) async {
    // Refresh charges list from server after payment
    add(const FetchChargesEvent(page: 1));
  }

  Future<void> _onPaymentFailed(
    PaymentFailedEvent event,
    Emitter<FinancialState> emit,
  ) async {
    emit(FinancialErrorState(errorMessage: event.errorMessage));
  }
}
