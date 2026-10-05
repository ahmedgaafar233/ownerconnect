import 'package:equatable/equatable.dart';

import '../../data/models/visitor_pass_model.dart';

abstract class VisitorPassState extends Equatable {
  const VisitorPassState();

  @override
  List<Object?> get props => [];
}

class VisitorPassInitialState extends VisitorPassState {}

class VisitorPassLoadingState extends VisitorPassState {}

class VisitorPassesLoadedState extends VisitorPassState {
  final List<VisitorPassModel> passes;

  const VisitorPassesLoadedState({required this.passes});

  @override
  List<Object?> get props => [passes];
}

class VisitorPassCreatedState extends VisitorPassState {
  final VisitorPassModel pass;

  const VisitorPassCreatedState({required this.pass});

  @override
  List<Object?> get props => [pass];
}

class VisitorPassErrorState extends VisitorPassState {
  final String message;

  const VisitorPassErrorState({required this.message});

  @override
  List<Object?> get props => [message];
}
