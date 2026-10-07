import 'package:equatable/equatable.dart';

import '../../../../core/utils/media_url.dart';
import '../../data/models/profile_unit.dart';

abstract class ProfileState extends Equatable {
  const ProfileState();

  @override
  List<Object?> get props => [];
}

class ProfileLoadingState extends ProfileState {
  const ProfileLoadingState();
}

class ProfileLoadedState extends ProfileState {
  final String fullname;
  final String phone;
  final String role;
  final String resortName;
  final String? resortLogoUrl;
  final List<ProfileUnit> units;

  final bool isSaving;

  /// True for exactly the one state emitted when a name save succeeds, so the
  /// screen can confirm it once.
  final bool justSaved;
  final String? saveError;

  const ProfileLoadedState({
    required this.fullname,
    required this.phone,
    required this.role,
    required this.resortName,
    this.resortLogoUrl,
    this.units = const [],
    this.isSaving = false,
    this.justSaved = false,
    this.saveError,
  });

  factory ProfileLoadedState.fromProfile(Map<String, dynamic> profile) {
    return ProfileLoadedState(
      fullname: profile['fullname'] as String? ?? '',
      phone: profile['phone'] as String? ?? '',
      role: profile['role'] as String? ?? 'OWNER',
      resortName: profile['resort_name'] as String? ?? '',
      resortLogoUrl: resolveMediaUrl(profile['resort_logo_url'] as String?),
      units: ProfileUnit.listFrom(profile['units']),
    );
  }

  ProfileLoadedState copyWith({
    String? fullname,
    bool? isSaving,
    bool justSaved = false,
    String? saveError,
  }) {
    return ProfileLoadedState(
      fullname: fullname ?? this.fullname,
      phone: phone,
      role: role,
      resortName: resortName,
      resortLogoUrl: resortLogoUrl,
      units: units,
      isSaving: isSaving ?? this.isSaving,
      justSaved: justSaved,
      saveError: saveError,
    );
  }

  /// A name if they've set one, else their phone — same rule as the drawer.
  String get displayName => fullname.trim().isNotEmpty ? fullname.trim() : phone;

  bool get isTenant => role == 'TENANT';

  @override
  List<Object?> get props =>
      [fullname, phone, role, resortName, resortLogoUrl, units, isSaving, justSaved, saveError];
}

class ProfileErrorState extends ProfileState {
  final String message;

  const ProfileErrorState(this.message);

  @override
  List<Object?> get props => [message];
}
