import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../../firebase_options.dart';
import '../../features/auth/data/repositories/firebase_auth_repository.dart';
import '../../features/auth/presentation/bloc/auth_bloc.dart';
import '../../features/financial/data/repositories/financial_repository.dart';
import '../../features/notifications/data/repositories/notification_repository.dart';
import '../../features/support/data/repositories/support_repository.dart';
import '../localization/locale_cubit.dart';
import '../network/dio_client.dart';

/// Everything the widget tree needs, built once before runApp. Keeps
/// main.dart down to "load dependencies, run the app" — no env/Firebase/DI
/// wiring lives there.
class AppDependencies {
  final AuthBloc authBloc;
  final FinancialRepository financialRepository;
  final SupportRepository supportRepository;
  final NotificationRepository notificationRepository;
  final LocaleCubit localeCubit;

  const AppDependencies({
    required this.authBloc,
    required this.financialRepository,
    required this.supportRepository,
    required this.notificationRepository,
    required this.localeCubit,
  });

  static Future<AppDependencies> bootstrap() async {
    try {
      await dotenv.load(fileName: ".env");
    } catch (_) {}

    try {
      await Firebase.initializeApp(
        options: DefaultFirebaseOptions.currentPlatform,
      );
    } catch (_) {
      // Firebase initialization fallback (e.g. dev-bypass mode)
    }

    try {
      // Must be called exactly once before GoogleSignIn.instance.authenticate().
      // serverClientId is the "Web client (auto created by Google Service)"
      // OAuth client id — copy it from the re-downloaded google-services.json
      // (oauth_client entries with client_type 3) once Google sign-in is
      // enabled in the Firebase console.
      await GoogleSignIn.instance.initialize(
        serverClientId: dotenv.env['GOOGLE_SERVER_CLIENT_ID'],
      );
    } catch (_) {
      // No Google client configured yet — the Google sign-in button will
      // surface its own error when tapped rather than blocking app startup.
    }

    final dioClient = DioClient();
    final authRepository = FirebaseAuthRepository(dio: dioClient.dio);

    final localeCubit = LocaleCubit();
    await localeCubit.load();

    return AppDependencies(
      authBloc: AuthBloc(repository: authRepository),
      localeCubit: localeCubit,
      financialRepository: FinancialRepository(dio: dioClient.dio),
      supportRepository: SupportRepository(dio: dioClient.dio),
      notificationRepository: NotificationRepository(dio: dioClient.dio),
    );
  }
}
