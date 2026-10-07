import 'package:equatable/equatable.dart';

import '../../data/models/lease_model.dart';

abstract class LeaseState extends Equatable {
  const LeaseState();

  @override
  List<Object?> get props => [];
}

class LeaseInitialState extends LeaseState {
  const LeaseInitialState();
}

class LeaseWorkingState extends LeaseState {
  const LeaseWorkingState();
}

class LeaseCreatedState extends LeaseState {
  final LeaseModel lease;

  /// Adults or papers that didn't upload after the rental itself was
  /// registered — the owner adds them again from the rental's details.
  final int failedUploads;

  const LeaseCreatedState(this.lease, {this.failedUploads = 0});

  @override
  List<Object?> get props => [lease, failedUploads];
}

/// A change to a rental the screen is showing (an adult or paper added or
/// removed, an extension): the new version of it.
class LeaseChangedState extends LeaseState {
  final LeaseModel lease;

  /// Bumped on every change so two identical results in a row still notify.
  final int revision;

  const LeaseChangedState(this.lease, this.revision);

  @override
  List<Object?> get props => [lease, revision];
}

/// A renewal: a new rental (the old one stays as history).
class LeaseRenewedState extends LeaseState {
  final LeaseModel lease;

  const LeaseRenewedState(this.lease);

  @override
  List<Object?> get props => [lease];
}

class LeaseEndedState extends LeaseState {
  final LeaseModel lease;

  const LeaseEndedState(this.lease);

  @override
  List<Object?> get props => [lease];
}

class LeaseErrorState extends LeaseState {
  final String message;

  const LeaseErrorState(this.message);

  @override
  List<Object?> get props => [message];
}
