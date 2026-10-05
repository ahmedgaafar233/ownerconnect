import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/repositories/financial_repository.dart';
import 'financial_event.dart';
import 'financial_state.dart';

class FinancialBloc extends Bloc<FinancialEvent, FinancialState> {
  final FinancialRepository repository;

  FinancialBloc({required this.repository}) : super(const FinancialInitialState()) {
    on<FetchChargesEvent>(_onFetchCharges);
    on<FetchChargeSummaryEvent>(_onFetchChargeSummary);
    on<InitiatePaymentEvent>(_onInitiatePayment);
    on<PaymentCompletedEvent>(_onPaymentCompleted);
    on<PaymentFailedEvent>(_onPaymentFailed);
    on<DeferChargeEvent>(_onDeferCharge);
    on<CreatePaymentPlanEvent>(_onCreatePaymentPlan);
  }

  Future<void> _onFetchCharges(
    FetchChargesEvent event,
    Emitter<FinancialState> emit,
  ) async {
    final currentState = state;

    if (event.page == 1) {
      emit(FinancialLoadingState(summary: state.summary));
      try {
        final charges = await repository.getCharges(
          page: 1,
          type: event.typeFilter,
          unpaidOnly: event.unpaidOnly,
          year: event.year,
          month: event.month,
        );
        emit(ChargesLoadedState(
          charges: charges,
          hasReachedMax: charges.length < 15,
          currentPage: 1,
          isFetchingMore: false,
          summary: state.summary,
        ));
      } catch (e) {
        emit(FinancialErrorState(errorMessage: e.toString(), summary: state.summary));
      }
    } else if (currentState is ChargesLoadedState && !currentState.hasReachedMax && !currentState.isFetchingMore) {
      emit(currentState.copyWith(isFetchingMore: true));
      try {
        final newCharges = await repository.getCharges(
          page: event.page,
          type: event.typeFilter,
          unpaidOnly: event.unpaidOnly,
          year: event.year,
          month: event.month,
        );

        if (newCharges.isEmpty) {
          emit(currentState.copyWith(hasReachedMax: true, isFetchingMore: false));
        } else {
          emit(ChargesLoadedState(
            charges: List.from(currentState.charges)..addAll(newCharges),
            hasReachedMax: newCharges.length < 15,
            currentPage: event.page,
            isFetchingMore: false,
            summary: state.summary,
          ));
        }
      } catch (e) {
        emit(currentState.copyWith(isFetchingMore: false));
      }
    }
  }

  Future<void> _onFetchChargeSummary(
    FetchChargeSummaryEvent event,
    Emitter<FinancialState> emit,
  ) async {
    try {
      final summary = await repository.getChargeSummary();
      final current = state;
      if (current is ChargesLoadedState) {
        emit(current.copyWith(summary: summary));
      } else if (current is FinancialErrorState) {
        emit(FinancialErrorState(errorMessage: current.errorMessage, summary: summary));
      } else if (current is FinancialLoadingState) {
        emit(FinancialLoadingState(summary: summary));
      } else {
        emit(FinancialInitialState(summary: summary));
      }
    } catch (_) {
      // Best-effort — the summary card just stays hidden/stale; the main
      // charges/payments list is unaffected.
    }
  }

  Future<void> _onInitiatePayment(
    InitiatePaymentEvent event,
    Emitter<FinancialState> emit,
  ) async {
    final currentState = state;
    emit(FinancialLoadingState(summary: state.summary));
    try {
      final session = await repository.initiateOnlinePayment(
        event.chargeIds,
        payAmount: event.payAmount,
        remainingDueDate: event.remainingDueDate,
      );
      emit(PaymentInitiatedState(paymentSession: session, summary: state.summary));
    } catch (e) {
      emit(FinancialErrorState(errorMessage: e.toString(), summary: state.summary));
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
    add(const FetchChargeSummaryEvent());
  }

  Future<void> _onPaymentFailed(
    PaymentFailedEvent event,
    Emitter<FinancialState> emit,
  ) async {
    emit(FinancialErrorState(errorMessage: event.errorMessage, summary: state.summary));
    // Without this, ChargesScreen (still mounted underneath the checkout
    // screen) has no ChargesLoadedState to render and goes blank once the
    // user backs out — confirmed on a real device.
    add(const FetchChargesEvent(page: 1));
  }

  Future<void> _onDeferCharge(
    DeferChargeEvent event,
    Emitter<FinancialState> emit,
  ) async {
    emit(FinancialLoadingState(summary: state.summary));
    try {
      await repository.deferCharge(chargeId: event.chargeId, deferredTo: event.deferredTo);
      emit(ChargeDeferredState(deferredTo: event.deferredTo, summary: state.summary));
    } catch (e) {
      emit(FinancialErrorState(errorMessage: e.toString(), summary: state.summary));
    }
    // Same lesson as payment completion/failure: refresh so the charges
    // list (still mounted underneath PaymentOptionsScreen) isn't left on a
    // state it doesn't know how to render.
    add(const FetchChargesEvent(page: 1));
    add(const FetchChargeSummaryEvent());
  }

  Future<void> _onCreatePaymentPlan(
    CreatePaymentPlanEvent event,
    Emitter<FinancialState> emit,
  ) async {
    emit(FinancialLoadingState(summary: state.summary));
    try {
      await repository.createPaymentPlan(chargeId: event.chargeId, installments: event.installments);
      emit(PaymentPlanCreatedState(summary: state.summary));
    } catch (e) {
      emit(FinancialErrorState(errorMessage: e.toString(), summary: state.summary));
    }
    add(const FetchChargesEvent(page: 1));
  }
}
