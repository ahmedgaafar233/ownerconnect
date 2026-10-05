import 'package:equatable/equatable.dart';

import '../../data/models/payment_model.dart';

abstract class PaymentHistoryState extends Equatable {
  const PaymentHistoryState();

  @override
  List<Object?> get props => [];
}

class PaymentHistoryInitialState extends PaymentHistoryState {
  const PaymentHistoryInitialState();
}

class PaymentHistoryLoadingState extends PaymentHistoryState {
  const PaymentHistoryLoadingState();
}

class PaymentHistoryLoadedState extends PaymentHistoryState {
  final List<PaymentModel> payments;
  final bool hasReachedMax;
  final int currentPage;
  final bool isFetchingMore;

  const PaymentHistoryLoadedState({
    required this.payments,
    required this.hasReachedMax,
    this.currentPage = 1,
    this.isFetchingMore = false,
  });

  PaymentHistoryLoadedState copyWith({
    List<PaymentModel>? payments,
    bool? hasReachedMax,
    int? currentPage,
    bool? isFetchingMore,
  }) {
    return PaymentHistoryLoadedState(
      payments: payments ?? this.payments,
      hasReachedMax: hasReachedMax ?? this.hasReachedMax,
      currentPage: currentPage ?? this.currentPage,
      isFetchingMore: isFetchingMore ?? this.isFetchingMore,
    );
  }

  @override
  List<Object?> get props => [payments, hasReachedMax, currentPage, isFetchingMore];
}

class PaymentHistoryErrorState extends PaymentHistoryState {
  final String message;

  const PaymentHistoryErrorState({required this.message});

  @override
  List<Object?> get props => [message];
}
