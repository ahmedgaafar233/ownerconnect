import 'package:equatable/equatable.dart';
import '../../data/models/charge_model.dart';
import '../../data/models/charge_summary_model.dart';
import '../../data/models/payment_model.dart';

// summary rides on every state as a side-channel (mirrors
// NotificationState.unreadCount) so the combined-total card can render
// regardless of whatever the "primary" state (loading/loaded/error)
// currently is, without needing a second BlocProvider.
abstract class FinancialState extends Equatable {
  final ChargeSummaryModel? summary;

  const FinancialState({this.summary});

  @override
  List<Object?> get props => [summary];
}

class FinancialInitialState extends FinancialState {
  const FinancialInitialState({super.summary});
}

class FinancialLoadingState extends FinancialState {
  const FinancialLoadingState({super.summary});
}

class ChargesLoadedState extends FinancialState {
  final List<ChargeModel> charges;
  final bool hasReachedMax;
  final int currentPage;
  final bool isFetchingMore;

  const ChargesLoadedState({
    required this.charges,
    required this.hasReachedMax,
    this.currentPage = 1,
    this.isFetchingMore = false,
    super.summary,
  });

  ChargesLoadedState copyWith({
    List<ChargeModel>? charges,
    bool? hasReachedMax,
    int? currentPage,
    bool? isFetchingMore,
    ChargeSummaryModel? summary,
  }) {
    return ChargesLoadedState(
      charges: charges ?? this.charges,
      hasReachedMax: hasReachedMax ?? this.hasReachedMax,
      currentPage: currentPage ?? this.currentPage,
      isFetchingMore: isFetchingMore ?? this.isFetchingMore,
      summary: summary ?? this.summary,
    );
  }

  @override
  List<Object?> get props => [charges, hasReachedMax, currentPage, isFetchingMore, summary];
}

class PaymentInitiatedState extends FinancialState {
  final Map<String, dynamic> paymentSession;

  const PaymentInitiatedState({required this.paymentSession, super.summary});

  @override
  List<Object?> get props => [paymentSession, summary];
}

class FinancialErrorState extends FinancialState {
  final String errorMessage;

  const FinancialErrorState({required this.errorMessage, super.summary});

  @override
  List<Object?> get props => [errorMessage, summary];
}

class ChargeDeferredState extends FinancialState {
  final String deferredTo;

  const ChargeDeferredState({required this.deferredTo, super.summary});

  @override
  List<Object?> get props => [deferredTo, summary];
}

class PaymentPlanCreatedState extends FinancialState {
  const PaymentPlanCreatedState({super.summary});
}

class PaymentHistoryLoadedState extends FinancialState {
  final List<PaymentModel> payments;
  final bool hasReachedMax;
  final int currentPage;
  final bool isFetchingMore;

  const PaymentHistoryLoadedState({
    required this.payments,
    required this.hasReachedMax,
    this.currentPage = 1,
    this.isFetchingMore = false,
    super.summary,
  });

  PaymentHistoryLoadedState copyWith({
    List<PaymentModel>? payments,
    bool? hasReachedMax,
    int? currentPage,
    bool? isFetchingMore,
    ChargeSummaryModel? summary,
  }) {
    return PaymentHistoryLoadedState(
      payments: payments ?? this.payments,
      hasReachedMax: hasReachedMax ?? this.hasReachedMax,
      currentPage: currentPage ?? this.currentPage,
      isFetchingMore: isFetchingMore ?? this.isFetchingMore,
      summary: summary ?? this.summary,
    );
  }

  @override
  List<Object?> get props => [payments, hasReachedMax, currentPage, isFetchingMore, summary];
}
