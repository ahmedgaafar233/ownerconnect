import 'package:equatable/equatable.dart';

abstract class ProfileEvent extends Equatable {
  const ProfileEvent();

  @override
  List<Object?> get props => [];
}

class ProfileLoadRequested extends ProfileEvent {
  /// Reload in place — keep showing the current profile instead of swapping
  /// it for a spinner (after a rental is registered or ended).
  final bool refresh;

  const ProfileLoadRequested({this.refresh = false});

  @override
  List<Object?> get props => [refresh];
}

class ProfileNameSaved extends ProfileEvent {
  final String fullname;

  const ProfileNameSaved(this.fullname);

  @override
  List<Object?> get props => [fullname];
}
