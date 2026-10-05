import 'package:equatable/equatable.dart';

abstract class HomeTabEvent extends Equatable {
  const HomeTabEvent();

  @override
  List<Object?> get props => [];
}

class HomeTabSelected extends HomeTabEvent {
  final int index;

  const HomeTabSelected(this.index);

  @override
  List<Object?> get props => [index];
}
