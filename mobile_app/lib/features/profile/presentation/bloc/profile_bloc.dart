import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/api_error.dart';
import '../../../auth/data/repositories/auth_repository.dart';
import 'profile_event.dart';
import 'profile_state.dart';

/// The profile screen: who this person is, the units they have, and their name.
class ProfileBloc extends Bloc<ProfileEvent, ProfileState> {
  final AuthRepository repository;

  ProfileBloc({required this.repository}) : super(const ProfileLoadingState()) {
    on<ProfileLoadRequested>(_onLoad);
    on<ProfileNameSaved>(_onNameSaved);
  }

  Future<void> _onLoad(ProfileLoadRequested event, Emitter<ProfileState> emit) async {
    final keepShowing = event.refresh && state is ProfileLoadedState;
    if (!keepShowing) emit(const ProfileLoadingState());
    try {
      final profile = await repository.fetchAndPersistProfile();
      emit(ProfileLoadedState.fromProfile(profile));
    } catch (e) {
      // A failed in-place refresh keeps what's on screen.
      if (!keepShowing) emit(ProfileErrorState(apiErrorMessage(e)));
    }
  }

  Future<void> _onNameSaved(ProfileNameSaved event, Emitter<ProfileState> emit) async {
    final current = state;
    if (current is! ProfileLoadedState) return;
    emit(current.copyWith(isSaving: true));
    try {
      final profile = await repository.updateFullname(event.fullname.trim());
      emit(current.copyWith(
        fullname: profile['fullname'] as String? ?? event.fullname.trim(),
        isSaving: false,
        justSaved: true,
      ));
    } catch (e) {
      emit(current.copyWith(isSaving: false, saveError: apiErrorMessage(e)));
    }
  }
}
