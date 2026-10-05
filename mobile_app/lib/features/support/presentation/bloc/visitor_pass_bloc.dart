import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/api_error.dart';
import '../../data/repositories/support_repository.dart';
import 'visitor_pass_event.dart';
import 'visitor_pass_state.dart';

/// Gate / beach passes. Its own bloc, not part of [SupportBloc]: the Support
/// and Passes tabs are both alive at once, and sharing one bloc meant each
/// tab's load replaced the other's state — the Support tab went blank as soon
/// as the Passes tab loaded.
class VisitorPassBloc extends Bloc<VisitorPassEvent, VisitorPassState> {
  final SupportRepository repository;

  VisitorPassBloc({required this.repository}) : super(VisitorPassInitialState()) {
    on<FetchVisitorPassesEvent>(_onFetch);
    on<CreateVisitorPassEvent>(_onCreate);
  }

  Future<void> _onFetch(FetchVisitorPassesEvent event, Emitter<VisitorPassState> emit) async {
    if (event.page == 1 && !event.refresh) emit(VisitorPassLoadingState());
    try {
      final passes = await repository.getVisitorPasses(page: event.page);
      emit(VisitorPassesLoadedState(passes: passes));
    } catch (e) {
      // A failed in-place refresh keeps the list the user is looking at.
      if (!event.refresh) emit(VisitorPassErrorState(message: apiErrorMessage(e)));
    }
  }

  Future<void> _onCreate(CreateVisitorPassEvent event, Emitter<VisitorPassState> emit) async {
    emit(VisitorPassLoadingState());
    try {
      final pass = await repository.createVisitorPass(
        unitId: event.unitId,
        passType: event.passType,
        visitorName: event.visitorName,
        nationalId: event.nationalId,
        carPlate: event.carPlate,
        startDate: event.startDate,
        endDate: event.endDate,
      );
      emit(VisitorPassCreatedState(pass: pass));
    } catch (e) {
      // Surfaces the server's own reason (e.g. the unit's card allowance is
      // used up) instead of a raw DioException string.
      emit(VisitorPassErrorState(message: apiErrorMessage(e)));
    }
  }
}
