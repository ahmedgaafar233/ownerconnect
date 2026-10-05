import 'package:flutter_bloc/flutter_bloc.dart';

import 'home_tab_event.dart';
import 'home_tab_state.dart';

class HomeTabBloc extends Bloc<HomeTabEvent, HomeTabState> {
  HomeTabBloc() : super(const HomeTabState(HomeTabs.charges)) {
    on<HomeTabSelected>((event, emit) => emit(HomeTabState(event.index)));
  }
}
