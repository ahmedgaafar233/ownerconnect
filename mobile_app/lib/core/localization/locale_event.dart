import 'package:equatable/equatable.dart';

abstract class LocaleEvent extends Equatable {
  const LocaleEvent();

  @override
  List<Object?> get props => [];
}

/// Fired once at startup: load a saved language preference, or — if the
/// owner never picked one — resolve the device's own system language
/// against the languages this app actually ships, falling back to English
/// rather than forcing Arabic on a non-Arabic, non-English owner.
class LocaleLoadRequested extends LocaleEvent {
  const LocaleLoadRequested();
}

class LocaleChanged extends LocaleEvent {
  final String languageCode;

  const LocaleChanged(this.languageCode);

  @override
  List<Object?> get props => [languageCode];
}
