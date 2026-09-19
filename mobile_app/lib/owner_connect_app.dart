import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'core/bootstrap/app_dependencies.dart';
import 'core/localization/locale_cubit.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';
import 'core/utils/app_localizations.dart';
import 'features/auth/presentation/bloc/auth_bloc.dart';
import 'features/auth/presentation/bloc/auth_state.dart';
import 'features/financial/presentation/bloc/financial_bloc.dart';
import 'features/notifications/presentation/bloc/notification_bloc.dart';
import 'features/notifications/presentation/bloc/notification_event.dart';
import 'features/support/presentation/bloc/support_bloc.dart';

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
  late final _routerConfig = AppRouter.build(widget.dependencies.authBloc);
  late final NotificationBloc _notificationBloc =
      NotificationBloc(repository: widget.dependencies.notificationRepository);

  @override
  void initState() {
    super.initState();
    // FcmService is built once in AppDependencies.bootstrap(), before this
    // widget (and therefore NotificationBloc) exists — wire the foreground
    // callback now that both are available, so a push that arrives while the
    // app is open refreshes the bell badge.
    widget.dependencies.fcmService.onForegroundMessage = (_) {
      _notificationBloc.add(const FetchUnreadCountEvent());
    };
  }

  @override
  void dispose() {
    _notificationBloc.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider.value(value: widget.dependencies.authBloc),
        BlocProvider.value(value: widget.dependencies.localeCubit),
        BlocProvider(create: (_) => FinancialBloc(repository: widget.dependencies.financialRepository)),
        BlocProvider(create: (_) => SupportBloc(repository: widget.dependencies.supportRepository)),
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
        child: BlocBuilder<LocaleCubit, Locale>(
          builder: (context, locale) {
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
              supportedLocales: const [
                Locale('en'),
                Locale('ar'),
              ],
              locale: locale,
              routerConfig: _routerConfig,
            );
          },
        ),
      ),
    );
  }
}
