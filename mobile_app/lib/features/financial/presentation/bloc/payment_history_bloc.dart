import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/api_error.dart';
import '../../data/repositories/financial_repository.dart';
import 'payment_history_event.dart';
import 'payment_history_state.dart';

/// Payment history, scoped to its own screen. It used to share
/// [FinancialBloc] with the charges page, so opening the history replaced the
/// charges page's state and — once the owner came back — left it blank
/// ("the invoices disappeared"). Its own bloc means neither can clobber the
/// other.
class PaymentHistoryBloc extends Bloc<PaymentHistoryEvent, PaymentHistoryState> {
  final FinancialRepository repository;

  PaymentHistoryBloc({required this.repository}) : super(const PaymentHistoryInitialState()) {
    on<FetchPaymentHistoryEvent>(_onFetch);
  }

  Future<void> _onFetch(FetchPaymentHistoryEvent event, Emitter<PaymentHistoryState> emit) async {
    final current = state;

    if (event.page == 1) {
      emit(const PaymentHistoryLoadingState());
      try {
        final payments = await repository.getPaymentHistory(page: 1, year: event.year, month: event.month);
        emit(PaymentHistoryLoadedState(
          payments: payments,
          hasReachedMax: payments.length < 15,
          currentPage: 1,
        ));
      } catch (e) {
        emit(PaymentHistoryErrorState(message: apiErrorMessage(e)));
      }
    } else if (current is PaymentHistoryLoadedState && !current.hasReachedMax && !current.isFetchingMore) {
      emit(current.copyWith(isFetchingMore: true));
      try {
        final more = await repository.getPaymentHistory(page: event.page, year: event.year, month: event.month);
        emit(more.isEmpty
            ? current.copyWith(hasReachedMax: true, isFetchingMore: false)
            : PaymentHistoryLoadedState(
                payments: [...current.payments, ...more],
                hasReachedMax: more.length < 15,
                currentPage: event.page,
              ));
      } catch (_) {
        emit(current.copyWith(isFetchingMore: false));
      }
    }
  }
}
