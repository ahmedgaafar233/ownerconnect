import 'package:equatable/equatable.dart';

/// Which tab of the home shell is showing. A bloc (not local widget state) so
/// something outside the shell — tapping a notification — can switch tabs.
class HomeTabState extends Equatable {
  final int index;

  const HomeTabState(this.index);

  @override
  List<Object?> get props => [index];
}

/// The tabs, by position in the bottom bar.
abstract class HomeTabs {
  static const charges = 0;
  static const support = 1;
  static const passes = 2;
}
