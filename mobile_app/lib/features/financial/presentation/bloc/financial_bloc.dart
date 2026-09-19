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
    on<DeferChargeEvent>(_onDeferCharge);
    on<CreatePaymentPlanEvent>(_onCreatePaymentPlan);
    on<FetchPaymentHistoryEvent>(_onFetchPaymentHistory);
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
    // Without this, ChargesScreen (still mounted underneath the checkout
    // screen) has no ChargesLoadedState to render and goes blank once the
    // user backs out — confirmed on a real device.
    add(const FetchChargesEvent(page: 1));
  }

  Future<void> _onDeferCharge(
    DeferChargeEvent event,
    Emitter<FinancialState> emit,
  ) async {
    emit(FinancialLoadingState());
    try {
      await repository.deferCharge(chargeId: event.chargeId, deferredTo: event.deferredTo);
      emit(ChargeDeferredState(deferredTo: event.deferredTo));
    } catch (e) {
      emit(FinancialErrorState(errorMessage: e.toString()));
    }
    // Same lesson as payment completion/failure: refresh so the charges
    // list (still mounted underneath PaymentOptionsScreen) isn't left on a
    // state it doesn't know how to render.
    add(const FetchChargesEvent(page: 1));
  }

  Future<void> _onCreatePaymentPlan(
    CreatePaymentPlanEvent event,
    Emitter<FinancialState> emit,
  ) async {
    emit(FinancialLoadingState());
    try {
      await repository.createPaymentPlan(chargeId: event.chargeId, installments: event.installments);
      emit(const PaymentPlanCreatedState());
    } catch (e) {
      emit(FinancialErrorState(errorMessage: e.toString()));
    }
    add(const FetchChargesEvent(page: 1));
  }

  Future<void> _onFetchPaymentHistory(
    FetchPaymentHistoryEvent event,
    Emitter<FinancialState> emit,
  ) async {
    final currentState = state;

    if (event.page == 1) {
      emit(FinancialLoadingState());
      try {
        final payments = await repository.getPaymentHistory(page: 1);
        emit(PaymentHistoryLoadedState(
          payments: payments,
          hasReachedMax: payments.length < 15,
          currentPage: 1,
          isFetchingMore: false,
        ));
      } catch (e) {
        emit(FinancialErrorState(errorMessage: e.toString()));
      }
    } else if (currentState is PaymentHistoryLoadedState &&
        !currentState.hasReachedMax &&
        !currentState.isFetchingMore) {
      emit(currentState.copyWith(isFetchingMore: true));
      try {
        final newPayments = await repository.getPaymentHistory(page: event.page);
        if (newPayments.isEmpty) {
          emit(currentState.copyWith(hasReachedMax: true, isFetchingMore: false));
        } else {
          emit(PaymentHistoryLoadedState(
            payments: List.from(currentState.payments)..addAll(newPayments),
            hasReachedMax: newPayments.length < 15,
            currentPage: event.page,
            isFetchingMore: false,
          ));
        }
      } catch (e) {
        emit(currentState.copyWith(isFetchingMore: false));
      }
    }
  }
}
