import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'core/bootstrap/app_dependencies.dart';
import 'core/localization/locale_bloc.dart';
import 'core/localization/locale_state.dart';
import 'core/router/app_router.dart';
import 'core/router/splash_gate.dart';
import 'core/services/notification_router.dart';
import 'core/theme/app_theme.dart';
import 'core/utils/app_localizations.dart';
import 'features/auth/presentation/bloc/auth_bloc.dart';
import 'features/auth/presentation/bloc/auth_state.dart';
import 'features/financial/presentation/bloc/financial_bloc.dart';
import 'features/home/presentation/bloc/home_tab_bloc.dart';
import 'features/notifications/presentation/bloc/notification_bloc.dart';
import 'features/notifications/presentation/bloc/notification_event.dart';
import 'features/support/presentation/bloc/support_bloc.dart';
import 'features/support/presentation/bloc/support_event.dart';
import 'features/support/presentation/bloc/visitor_pass_bloc.dart';
import 'features/support/presentation/bloc/visitor_pass_event.dart';

/// Root widget: provides the app-wide blocs and configures MaterialApp. All
/// setup work (env, Firebase, repositories) already happened in
/// [AppDependencies.bootstrap] before this is built.
class OwnerConnectApp extends StatefulWidget {
  final AppDependencies dependencies;

  const OwnerConnectApp({Key? key, required this.dependencies}) : super(key: key);

  @override
  State<OwnerConnectApp> createState() => _OwnerConnectAppState();
}

class _OwnerConnectAppState extends State<OwnerConnectApp> {
  // Built exactly once, in State rather than in build() — this must never be
  // recreated on a language switch. Doing so recreates the whole
  // GoRouter/Navigator tree, which was silently wiping out in-progress
  // screens/tab selection (confirmed on a real device: e.g. the Support tab
  // appeared to lose its just-created tickets after switching language,
  // because the entire navigation stack — not just the text — had been
  // rebuilt from scratch).
  final SplashGate _splashGate = SplashGate();
  late final _routerConfig = AppRouter.build(
    widget.dependencies.authBloc,
    widget.dependencies.resortSelection,
    splashGate: _splashGate,
  );
  late final NotificationBloc _notificationBloc =
      NotificationBloc(repository: widget.dependencies.notificationRepository);
  // Owned here (not created lazily by a BlocProvider) so a push that arrives
  // while the app is open can refresh whichever list it concerns.
  late final HomeTabBloc _homeTabBloc = HomeTabBloc();
  late final NotificationRouter _notificationRouter =
      NotificationRouter(router: _routerConfig, homeTabs: _homeTabBloc);
  late final SupportBloc _supportBloc = SupportBloc(repository: widget.dependencies.supportRepository);
  late final VisitorPassBloc _visitorPassBloc = VisitorPassBloc(repository: widget.dependencies.supportRepository);

  @override
  void initState() {
    super.initState();
    // FcmService is built once in AppDependencies.bootstrap(), before this
    // widget (and therefore NotificationBloc) exists — wire the foreground
    // callback now that both are available, so a push that arrives while the
    // app is open refreshes the bell badge.
    widget.dependencies.fcmService.onNotificationTap = (data) => _notificationRouter.open(data);
    widget.dependencies.fcmService.onForegroundMessage = (message) {
      _notificationBloc.add(const FetchUnreadCountEvent());
      // A decision on a pass or an update on a request changes what the
      // lists show — reload them in place rather than leave them stale.
      switch (message.data['type']) {
        case 'pass_decided':
          _visitorPassBloc.add(const FetchVisitorPassesEvent(refresh: true));
          break;
        case 'ticket_status':
        case 'ticket_reply':
          _supportBloc.add(const FetchTicketsEvent(page: 1));
          break;
      }
    };
  }

  @override
  void dispose() {
    _notificationBloc.close();
    _homeTabBloc.close();
    _supportBloc.close();
    _visitorPassBloc.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        RepositoryProvider.value(value: widget.dependencies.resortRepository),
        RepositoryProvider.value(value: _notificationRouter),
        // ResortSelection is a ValueNotifier — needs ChangeNotifierProvider
        // (not a plain RepositoryProvider.value) so context.watch<>() in
        // ResortWelcomeScreen actually rebuilds when it changes.
        ChangeNotifierProvider.value(value: widget.dependencies.resortSelection),
        ChangeNotifierProvider.value(value: _splashGate),
      ],
      child: MultiBlocProvider(
        providers: [
          BlocProvider.value(value: widget.dependencies.authBloc),
          BlocProvider.value(value: widget.dependencies.localeBloc),
          BlocProvider(create: (_) => FinancialBloc(repository: widget.dependencies.financialRepository)),
          BlocProvider.value(value: _homeTabBloc),
          BlocProvider.value(value: _supportBloc),
          BlocProvider.value(value: _visitorPassBloc),
          BlocProvider.value(value: _notificationBloc),
        ],
        child: BlocListener<AuthBloc, AuthState>(
          // Registering an FCM token needs an authenticated request (the
          // backend endpoint requires IsAuthenticated), and this fires exactly
          // once per sign-in across every auth path (OTP, dev-bypass, Google,
          // email, account-link, and the startup session check) since they all
          // funnel through AuthBloc._resolveProfile emitting AuthenticatedState.
          listenWhen: (previous, current) => current is AuthenticatedState && previous is! AuthenticatedState,
          listener: (context, state) {
            widget.dependencies.fcmService.initialize();
            widget.dependencies.fcmService.registerCurrentToken();
          },
          child: BlocBuilder<LocaleBloc, LocaleState>(
            builder: (context, localeState) {
              return MaterialApp.router(
                title: 'OwnerConnect',
                debugShowCheckedModeBanner: false,
                theme: AppTheme.lightTheme,
                localizationsDelegates: const [
                  AppLocalizationsDelegate(),
                  GlobalMaterialLocalizations.delegate,
                  GlobalWidgetsLocalizations.delegate,
                  GlobalCupertinoLocalizations.delegate,
                ],
                supportedLocales: kSupportedLocales,
                locale: localeState.locale,
                routerConfig: _routerConfig,
              );
            },
          ),
        ),
      ),
    );
  }
}
