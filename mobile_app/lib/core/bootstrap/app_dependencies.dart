import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

import '../../firebase_options.dart';
import '../../features/auth/data/repositories/firebase_auth_repository.dart';
import '../../features/auth/data/repositories/resort_repository.dart';
import '../../features/auth/data/resort_selection.dart';
import '../../features/auth/presentation/bloc/auth_bloc.dart';
import '../../features/financial/data/repositories/financial_repository.dart';
import '../../features/notifications/data/repositories/notification_repository.dart';
import '../../features/profile/data/repositories/lease_repository.dart';
import '../../features/profile/data/repositories/payment_method_repository.dart';
import '../../features/support/data/repositories/support_repository.dart';
import '../localization/locale_bloc.dart';
import '../localization/locale_event.dart';
import '../network/dio_client.dart';
import '../services/fcm_service.dart';
import 'google_sign_in_init.dart';

/// Everything the widget tree needs, built once before runApp. Keeps
/// main.dart down to "load dependencies, run the app" — no env/Firebase/DI
/// wiring lives there.
class AppDependencies {
  final AuthBloc authBloc;
  final FinancialRepository financialRepository;
  final SupportRepository supportRepository;
  final LeaseRepository leaseRepository;
  final PaymentMethodRepository paymentMethodRepository;
  final NotificationRepository notificationRepository;
  final FcmService fcmService;
  final LocaleBloc localeBloc;
  final ResortRepository resortRepository;
  final ResortSelection resortSelection;

  const AppDependencies({
    required this.authBloc,
    required this.financialRepository,
    required this.supportRepository,
    required this.leaseRepository,
    required this.paymentMethodRepository,
    required this.notificationRepository,
    required this.fcmService,
    required this.localeBloc,
    required this.resortRepository,
    required this.resortSelection,
  });

  static Future<void> _loadEnv() async {
    try {
      await dotenv.load(fileName: ".env");
    } catch (_) {}
  }

  static Future<void> _initFirebase() async {
    try {
      await Firebase.initializeApp(
        options: DefaultFirebaseOptions.currentPlatform,
      );
    } catch (_) {
      // Firebase initialization fallback (e.g. dev-bypass mode)
    }
  }

  static Future<AppDependencies> bootstrap() async {
    final localeBloc = LocaleBloc();
    final localeLoaded = localeBloc.stream.first;
    localeBloc.add(const LocaleLoadRequested());

    // The start-up steps that don't depend on each other run side by side —
    // this is what the native launch screen is held up for, so the time it
    // takes is the slowest one, not their sum.
    final results = await Future.wait<Object?>([
      _loadEnv(),
      _initFirebase(),
      localeLoaded,
      ResortSelection.load(),
    ]);
    final resortSelection = results[3] as ResortSelection;

    // Not awaited: it's a network round trip and nothing needs it until the
    // owner actually taps "Sign in with Google" (which waits for it). Needs
    // the .env loaded above for its client id.
    GoogleSignInInit.start();

    final dioClient = DioClient();
    final authRepository = FirebaseAuthRepository(dio: dioClient.dio);

    return AppDependencies(
      authBloc: AuthBloc(repository: authRepository),
      localeBloc: localeBloc,
      financialRepository: FinancialRepository(dio: dioClient.dio),
      supportRepository: SupportRepository(dio: dioClient.dio),
      leaseRepository: LeaseRepository(dio: dioClient.dio),
      paymentMethodRepository: PaymentMethodRepository(dio: dioClient.dio),
      notificationRepository: NotificationRepository(dio: dioClient.dio),
      fcmService: FcmService(dioClient.dio),
      resortRepository: ResortRepository(dio: dioClient.dio),
      resortSelection: resortSelection,
    );
  }
}
