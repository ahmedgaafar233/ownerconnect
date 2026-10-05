import 'package:equatable/equatable.dart';

abstract class VisitorPassEvent extends Equatable {
  const VisitorPassEvent();

  @override
  List<Object?> get props => [];
}

class FetchVisitorPassesEvent extends VisitorPassEvent {
  final int page;

  /// Reload in place — keep showing the current list instead of swapping it
  /// for a spinner. Used for pull-to-refresh and when a push says a pass was
  /// decided while the list is on screen.
  final bool refresh;

  const FetchVisitorPassesEvent({this.page = 1, this.refresh = false});

  @override
  List<Object?> get props => [page, refresh];
}

class CreateVisitorPassEvent extends VisitorPassEvent {
  final int unitId;
  final String passType;
  final String visitorName;
  final String nationalId;
  final String carPlate;

  /// Calendar dates (yyyy-MM-dd) — the server turns them into the resort's own
  /// days, so the phone's time zone can't shift a visit onto another day.
  final String startDate;
  final String endDate;

  const CreateVisitorPassEvent({
    required this.unitId,
    required this.passType,
    required this.visitorName,
    required this.nationalId,
    required this.carPlate,
    required this.startDate,
    required this.endDate,
  });

  @override
  List<Object?> get props => [
        unitId,
        passType,
        visitorName,
        nationalId,
        carPlate,
        startDate,
        endDate,
      ];
}
