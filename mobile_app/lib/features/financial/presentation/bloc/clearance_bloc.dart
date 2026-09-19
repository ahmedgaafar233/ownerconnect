import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/repositories/financial_repository.dart';
import 'clearance_event.dart';
import 'clearance_state.dart';

class ClearanceBloc extends Bloc<ClearanceEvent, ClearanceState> {
  final FinancialRepository repository;

  ClearanceBloc({required this.repository}) : super(const ClearanceState()) {
    on<GenerateClearanceEvent>(_onGenerate);
    on<FetchClearanceHistoryEvent>(_onFetchHistory);
  }

  // Both handlers below always read `state` fresh right before emitting
  // (never a pre-await local) — flutter_bloc processes events for
  // different types concurrently by default, so a handler that captured
  // `state` before its own `await` could silently discard whatever the
  // other handler wrote in the meantime. Confirmed as a real bug class in
  // FinancialBloc earlier this session; avoided here from the start.

  Future<void> _onGenerate(
    GenerateClearanceEvent event,
    Emitter<ClearanceState> emit,
  ) async {
    emit(ClearanceState(
      generateStatus: ClearanceGenerateStatus.loading,
      latestStatement: state.latestStatement,
      historyStatus: state.historyStatus,
      history: state.history,
    ));
    try {
      final statement = await repository.generateClearance(
        unitId: event.unitId,
        asOfDate: event.asOfDate,
      );
      emit(ClearanceState(
        generateStatus: ClearanceGenerateStatus.success,
        latestStatement: statement,
        historyStatus: state.historyStatus,
        history: [statement, ...state.history],
        historyError: state.historyError,
      ));
    } catch (e) {
      emit(ClearanceState(
        generateStatus: ClearanceGenerateStatus.error,
        generateError: e.toString(),
        latestStatement: state.latestStatement,
        historyStatus: state.historyStatus,
        history: state.history,
        historyError: state.historyError,
      ));
    }
  }

  Future<void> _onFetchHistory(
    FetchClearanceHistoryEvent event,
    Emitter<ClearanceState> emit,
  ) async {
    emit(ClearanceState(
      generateStatus: state.generateStatus,
      latestStatement: state.latestStatement,
      generateError: state.generateError,
      historyStatus: ClearanceHistoryStatus.loading,
      history: state.history,
    ));
    try {
      final history = await repository.getClearanceHistory(unitId: event.unitId);
      emit(ClearanceState(
        generateStatus: state.generateStatus,
        latestStatement: state.latestStatement,
        generateError: state.generateError,
        historyStatus: ClearanceHistoryStatus.success,
        history: history,
      ));
    } catch (e) {
      emit(ClearanceState(
        generateStatus: state.generateStatus,
        latestStatement: state.latestStatement,
        generateError: state.generateError,
        historyStatus: ClearanceHistoryStatus.error,
        history: state.history,
        historyError: e.toString(),
      ));
    }
  }
}
