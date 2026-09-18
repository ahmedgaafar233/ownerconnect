import 'package:flutter/material.dart';

import 'core/bootstrap/app_dependencies.dart';
import 'owner_connect_app.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final dependencies = await AppDependencies.bootstrap();
  runApp(OwnerConnectApp(dependencies: dependencies));
}
