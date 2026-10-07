import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/api_error.dart';
import '../../data/repositories/payment_method_repository.dart';
import 'payment_methods_event.dart';
import 'payment_methods_state.dart';

/// The person's saved ways to pay (wallet, InstaPay, Fawry).
class PaymentMethodsBloc extends Bloc<PaymentMethodsEvent, PaymentMethodsState> {
  final PaymentMethodRepository repository;

  PaymentMethodsBloc({required this.repository}) : super(const PaymentMethodsLoadingState()) {
    on<PaymentMethodsLoadRequested>(_onLoad);
    on<PaymentMethodAdded>(_onAdded);
    on<PaymentMethodRemoved>(_onRemoved);
    on<PaymentMethodMadeDefault>(_onMadeDefault);
  }

  Future<void> _onLoad(PaymentMethodsLoadRequested event, Emitter<PaymentMethodsState> emit) async {
    emit(const PaymentMethodsLoadingState());
    try {
      final methods = await repository.list();
      final options = await repository.options();
      emit(PaymentMethodsLoadedState(methods: methods, options: options));
    } catch (e) {
      emit(PaymentMethodsErrorState(apiErrorMessage(e)));
    }
  }

  /// Runs one change, then reloads the list so what's on screen is what the server has.
  Future<void> _change(Emitter<PaymentMethodsState> emit, Future<void> Function() change, {String? notice}) async {
    final current = state;
    if (current is! PaymentMethodsLoadedState) return;
    emit(current.copyWith(isBusy: true));
    try {
      await change();
      emit(current.copyWith(methods: await repository.list(), isBusy: false, notice: notice));
    } catch (e) {
      emit(current.copyWith(isBusy: false, error: apiErrorMessage(e)));
    }
  }

  Future<void> _onAdded(PaymentMethodAdded event, Emitter<PaymentMethodsState> emit) => _change(
        emit,
        () => repository.add(
          kind: event.kind,
          walletProvider: event.walletProvider,
          walletPhone: event.walletPhone,
          instapayAddress: event.instapayAddress,
        ),
        notice: 'saved',
      );

  Future<void> _onRemoved(PaymentMethodRemoved event, Emitter<PaymentMethodsState> emit) =>
      _change(emit, () => repository.remove(event.id), notice: 'removed');

  Future<void> _onMadeDefault(PaymentMethodMadeDefault event, Emitter<PaymentMethodsState> emit) =>
      _change(emit, () => repository.makeDefault(event.id));
}
