import 'package:equatable/equatable.dart';

abstract class FinancialEvent extends Equatable {
  const FinancialEvent();

  @override
  List<Object?> get props => [];
}

class FetchChargesEvent extends FinancialEvent {
  final int page;
  final String? typeFilter;
  final bool? unpaidOnly;

  const FetchChargesEvent({this.page = 1, this.typeFilter, this.unpaidOnly});

  @override
  List<Object?> get props => [page, typeFilter, unpaidOnly];
}

class InitiatePaymentEvent extends FinancialEvent {
  final List<int> chargeIds;

  const InitiatePaymentEvent({required this.chargeIds});

  @override
  List<Object?> get props => [chargeIds];
}

class PaymentCompletedEvent extends FinancialEvent {
  final String receiptNo;

  const PaymentCompletedEvent({required this.receiptNo});

  @override
  List<Object?> get props => [receiptNo];
}

class PaymentFailedEvent extends FinancialEvent {
  final String errorMessage;

  const PaymentFailedEvent({required this.errorMessage});

  @override
  List<Object?> get props => [errorMessage];
}

class DeferChargeEvent extends FinancialEvent {
  final int chargeId;
  final String deferredTo;

  const DeferChargeEvent({required this.chargeId, required this.deferredTo});

  @override
  List<Object?> get props => [chargeId, deferredTo];
}

class CreatePaymentPlanEvent extends FinancialEvent {
  final int chargeId;
  final List<Map<String, String>> installments;

  const CreatePaymentPlanEvent({required this.chargeId, required this.installments});

  @override
  List<Object?> get props => [chargeId, installments];
}
