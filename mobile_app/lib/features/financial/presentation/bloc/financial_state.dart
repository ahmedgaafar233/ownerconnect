import 'package:equatable/equatable.dart';
import '../../data/models/charge_model.dart';

abstract class FinancialState extends Equatable {
  const FinancialState();

  @override
  List<Object?> get props => [];
}

class FinancialInitialState extends FinancialState {}

class FinancialLoadingState extends FinancialState {}

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
  });

  ChargesLoadedState copyWith({
    List<ChargeModel>? charges,
    bool? hasReachedMax,
    int? currentPage,
    bool? isFetchingMore,
  }) {
    return ChargesLoadedState(
      charges: charges ?? this.charges,
      hasReachedMax: hasReachedMax ?? this.hasReachedMax,
      currentPage: currentPage ?? this.currentPage,
      isFetchingMore: isFetchingMore ?? this.isFetchingMore,
    );
  }

  @override
  List<Object?> get props => [charges, hasReachedMax, currentPage, isFetchingMore];
}

class PaymentInitiatedState extends FinancialState {
  final Map<String, dynamic> paymentSession;

  const PaymentInitiatedState({required this.paymentSession});

  @override
  List<Object?> get props => [paymentSession];
}

class FinancialErrorState extends FinancialState {
  final String errorMessage;

  const FinancialErrorState({required this.errorMessage});

  @override
  List<Object?> get props => [errorMessage];
}

class ChargeDeferredState extends FinancialState {
  final String deferredTo;

  const ChargeDeferredState({required this.deferredTo});

  @override
  List<Object?> get props => [deferredTo];
}

class PaymentPlanCreatedState extends FinancialState {
  const PaymentPlanCreatedState();
}
