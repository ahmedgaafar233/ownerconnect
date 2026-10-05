import 'package:equatable/equatable.dart';

abstract class PaymentHistoryEvent extends Equatable {
  const PaymentHistoryEvent();

  @override
  List<Object?> get props => [];
}

class FetchPaymentHistoryEvent extends PaymentHistoryEvent {
  final int page;
  final int? year;
  final int? month;

  const FetchPaymentHistoryEvent({this.page = 1, this.year, this.month});

  @override
  List<Object?> get props => [page, year, month];
}
