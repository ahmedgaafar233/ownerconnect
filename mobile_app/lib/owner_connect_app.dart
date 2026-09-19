import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'core/bootstrap/app_dependencies.dart';
import 'core/localization/locale_cubit.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';
import 'core/utils/app_localizations.dart';
import 'features/financial/presentation/bloc/financial_bloc.dart';
import 'features/notifications/presentation/bloc/notification_bloc.dart';
import 'features/support/presentation/bloc/support_bloc.dart';

/// Root widget: provides the app-wide blocs and configures MaterialApp. All
/// setup work (env, Firebase, repositories) already happened in
/// [AppDependencies.bootstrap] before this is built.
class OwnerConnectApp extends StatelessWidget {
  final AppDependencies dependencies;

  const OwnerConnectApp({Key? key, required this.dependencies}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    // Built exactly once, outside the locale-driven rebuild below — this
    // must never be recreated on a language switch. Doing so recreates the
    // whole GoRouter/Navigator tree, which was silently wiping out
    // in-progress screens/tab selection (confirmed on a real device: e.g.
    // the Support tab appeared to lose its just-created tickets after
    // switching language, because the entire navigation stack — not just
    // the text — had been rebuilt from scratch).
    final routerConfig = AppRouter.build(dependencies.authBloc);

    return MultiBlocProvider(
      providers: [
        BlocProvider.value(value: dependencies.authBloc),
        BlocProvider.value(value: dependencies.localeCubit),
        BlocProvider(create: (_) => FinancialBloc(repository: dependencies.financialRepository)),
        BlocProvider(create: (_) => SupportBloc(repository: dependencies.supportRepository)),
        BlocProvider(create: (_) => NotificationBloc(repository: dependencies.notificationRepository)),
      ],
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
            routerConfig: routerConfig,
          );
        },
      ),
    );
  }
}
