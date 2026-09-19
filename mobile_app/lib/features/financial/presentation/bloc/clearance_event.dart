import 'package:equatable/equatable.dart';

abstract class ClearanceEvent extends Equatable {
  const ClearanceEvent();

  @override
  List<Object?> get props => [];
}

class GenerateClearanceEvent extends ClearanceEvent {
  final int unitId;
  final DateTime? asOfDate;

  const GenerateClearanceEvent({required this.unitId, this.asOfDate});

  @override
  List<Object?> get props => [unitId, asOfDate];
}

class FetchClearanceHistoryEvent extends ClearanceEvent {
  final int? unitId;

  const FetchClearanceHistoryEvent({this.unitId});

  @override
  List<Object?> get props => [unitId];
}
