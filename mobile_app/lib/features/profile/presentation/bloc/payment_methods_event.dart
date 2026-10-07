import 'package:equatable/equatable.dart';

abstract class PaymentMethodsEvent extends Equatable {
  const PaymentMethodsEvent();

  @override
  List<Object?> get props => [];
}

class PaymentMethodsLoadRequested extends PaymentMethodsEvent {
  const PaymentMethodsLoadRequested();
}

class PaymentMethodAdded extends PaymentMethodsEvent {
  final String kind; // WALLET | INSTAPAY | FAWRY
  final String? walletProvider;

  /// E.164.
  final String? walletPhone;
  final String? instapayAddress;

  const PaymentMethodAdded({required this.kind, this.walletProvider, this.walletPhone, this.instapayAddress});

  @override
  List<Object?> get props => [kind, walletProvider, walletPhone, instapayAddress];
}

class PaymentMethodRemoved extends PaymentMethodsEvent {
  final int id;

  const PaymentMethodRemoved(this.id);

  @override
  List<Object?> get props => [id];
}

class PaymentMethodMadeDefault extends PaymentMethodsEvent {
  final int id;

  const PaymentMethodMadeDefault(this.id);

  @override
  List<Object?> get props => [id];
}
