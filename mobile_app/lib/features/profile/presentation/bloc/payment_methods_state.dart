import 'package:equatable/equatable.dart';

import '../../data/models/payment_method_model.dart';

abstract class PaymentMethodsState extends Equatable {
  const PaymentMethodsState();

  @override
  List<Object?> get props => [];
}

class PaymentMethodsLoadingState extends PaymentMethodsState {
  const PaymentMethodsLoadingState();
}

class PaymentMethodsLoadedState extends PaymentMethodsState {
  final List<PaymentMethodModel> methods;
  final PaymentMethodOptions options;
  final bool isBusy;

  /// One-shot notices for the screen: set on exactly the state that follows
  /// the change, cleared by the next one.
  final String? notice; // 'saved' | 'removed'
  final String? error;

  const PaymentMethodsLoadedState({
    required this.methods,
    required this.options,
    this.isBusy = false,
    this.notice,
    this.error,
  });

  PaymentMethodsLoadedState copyWith({
    List<PaymentMethodModel>? methods,
    bool? isBusy,
    String? notice,
    String? error,
  }) =>
      PaymentMethodsLoadedState(
        methods: methods ?? this.methods,
        options: options,
        isBusy: isBusy ?? this.isBusy,
        notice: notice,
        error: error,
      );

  bool get isFull => methods.length >= options.maxMethods;

  @override
  List<Object?> get props => [methods, options, isBusy, notice, error];
}

class PaymentMethodsErrorState extends PaymentMethodsState {
  final String message;

  const PaymentMethodsErrorState(this.message);

  @override
  List<Object?> get props => [message];
}
