import 'package:flutter/foundation.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/data/resort_selection.dart';
import '../../features/auth/presentation/bloc/auth_bloc.dart';
import '../../features/auth/presentation/bloc/auth_state.dart';
import '../../features/auth/presentation/screens/account_link_screen.dart';
import '../../features/auth/presentation/screens/otp_verification_screen.dart';
import '../../features/auth/presentation/screens/pending_resort_screen.dart';
import '../../features/auth/presentation/screens/phone_entry_screen.dart';
import '../../features/auth/presentation/screens/resort_picker_screen.dart';
import '../../features/auth/presentation/screens/resort_welcome_screen.dart';
import '../../features/auth/presentation/screens/splash_screen.dart';
import '../../features/home/presentation/screens/home_shell.dart';
import '../../features/notifications/presentation/screens/notifications_screen.dart';
import 'go_router_refresh_stream.dart';

const _resortPickerFlow = {'/select-resort', '/welcome-resort'};

/// The single tenant-lock gate for the whole app: every route decision comes
/// from AuthBloc's state, never from a screen navigating on its own. This is
/// what guarantees the app always lands on (and stays on) the signed-in
/// owner's own resort — see AuthenticatedState.resortName consumed by
/// HomeShell.
class AppRouter {
  static GoRouter build(AuthBloc authBloc, ResortSelection resortSelection) {
    return GoRouter(
      initialLocation: '/splash',
      refreshListenable: Listenable.merge([GoRouterRefreshStream(authBloc.stream), resortSelection]),
      redirect: (context, state) {
        final authState = authBloc.state;
        final location = state.matchedLocation;

        if (authState is AuthInitialState || authState is AuthLoadingState) {
          return location == '/splash' ? null : '/splash';
        }
        if (authState is UnauthenticatedState) {
          // First launch (no resort ever picked): show the resort picker →
          // welcome screen before login. Once a resort's been picked
          // (this run or a previous one), skip straight to /login — this is
          // purely local branding state, never a tenant switch (see
          // ResortSelection's doc comment).
          if (resortSelection.value == null) {
            return _resortPickerFlow.contains(location) ? null : '/select-resort';
          }
          if (_resortPickerFlow.contains(location)) return null;
          return location == '/login' ? null : '/login';
        }
        if (authState is OtpSentState) {
          return location == '/otp' ? null : '/otp';
        }
        if (authState is AccountLinkRequiredState) {
          return location == '/link-account' ? null : '/link-account';
        }
        if (authState is AwaitingResortAssignmentState) {
          return location == '/pending' ? null : '/pending';
        }
        if (authState is AuthenticatedState) {
          // Only bounce away from the pre-auth screens — any other route
          // (e.g. /notifications) is a normal in-app destination and must
          // not be redirected back to /home on every navigation.
          const preAuthLocations = ['/splash', '/login', '/otp', '/link-account', '/pending'];
          return preAuthLocations.contains(location) ? '/home' : null;
        }
        // AuthErrorState: stay put, the current screen already shows the
        // error via its own BlocConsumer listener.
        return null;
      },
      routes: [
        GoRoute(path: '/splash', builder: (_, __) => const SplashScreen()),
        GoRoute(path: '/select-resort', builder: (_, __) => const ResortPickerScreen()),
        GoRoute(path: '/welcome-resort', builder: (_, __) => const ResortWelcomeScreen()),
        GoRoute(path: '/login', builder: (_, __) => const PhoneEntryScreen()),
        GoRoute(path: '/otp', builder: (_, __) => const OtpVerificationScreen()),
        GoRoute(path: '/link-account', builder: (_, __) => const AccountLinkScreen()),
        GoRoute(path: '/pending', builder: (_, __) => const PendingResortScreen()),
        GoRoute(path: '/home', builder: (_, __) => const HomeShell()),
        GoRoute(path: '/notifications', builder: (_, __) => const NotificationsScreen()),
      ],
    );
  }
}
