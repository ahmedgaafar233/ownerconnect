import 'package:equatable/equatable.dart';
import '../../data/models/clearance_model.dart';

enum ClearanceGenerateStatus { idle, loading, success, error }

enum ClearanceHistoryStatus { idle, loading, success, error }

class ClearanceState extends Equatable {
  final ClearanceGenerateStatus generateStatus;
  final ClearanceStatementModel? latestStatement;
  final String? generateError;
  final ClearanceHistoryStatus historyStatus;
  final List<ClearanceStatementModel> history;
  final String? historyError;

  const ClearanceState({
    this.generateStatus = ClearanceGenerateStatus.idle,
    this.latestStatement,
    this.generateError,
    this.historyStatus = ClearanceHistoryStatus.idle,
    this.history = const [],
    this.historyError,
  });

  @override
  List<Object?> get props => [
        generateStatus,
        latestStatement,
        generateError,
        historyStatus,
        history,
        historyError,
      ];
}
