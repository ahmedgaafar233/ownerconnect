import 'package:flutter/material.dart';
import 'package:flutter_native_splash/flutter_native_splash.dart';

import 'core/bootstrap/app_dependencies.dart';
import 'owner_connect_app.dart';

void main() async {
  final widgetsBinding = WidgetsFlutterBinding.ensureInitialized();
  // Keeps the branded native launch screen (see pubspec.yaml's
  // flutter_native_splash config) up through Firebase/Google-Sign-In init —
  // previously a blank white screen for however long that took, with the
  // Dart SplashScreen only getting to appear (briefly) after it.
  FlutterNativeSplash.preserve(widgetsBinding: widgetsBinding);
  final dependencies = await AppDependencies.bootstrap();
  runApp(OwnerConnectApp(dependencies: dependencies));
  FlutterNativeSplash.remove();
}
