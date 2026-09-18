import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

import '../../firebase_options.dart';
import '../../features/auth/data/repositories/firebase_auth_repository.dart';
import '../../features/auth/presentation/bloc/auth_bloc.dart';
import '../../features/financial/data/repositories/financial_repository.dart';
import '../../features/support/data/repositories/support_repository.dart';
import '../network/dio_client.dart';

/// Everything the widget tree needs, built once before runApp. Keeps
/// main.dart down to "load dependencies, run the app" — no env/Firebase/DI
/// wiring lives there.
class AppDependencies {
  final AuthBloc authBloc;
  final FinancialRepository financialRepository;
  final SupportRepository supportRepository;

  const AppDependencies({
    required this.authBloc,
    required this.financialRepository,
    required this.supportRepository,
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

    final dioClient = DioClient();
    final authRepository = FirebaseAuthRepository(dio: dioClient.dio);

    return AppDependencies(
      authBloc: AuthBloc(repository: authRepository),
      financialRepository: FinancialRepository(dio: dioClient.dio),
      supportRepository: SupportRepository(dio: dioClient.dio),
    );
  }
}
