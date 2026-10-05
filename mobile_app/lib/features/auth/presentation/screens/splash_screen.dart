import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:provider/provider.dart';

import '../../../../core/router/splash_gate.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/widgets/owc_mark.dart';
import '../bloc/auth_bloc.dart';
import '../bloc/auth_event.dart';

/// Pure loading state while AuthBloc checks a stored session. The router's
/// redirect logic decides where to go next once AuthBloc emits a real state
/// — this screen makes no navigation decisions itself, except that it keeps
/// the router here ([SplashGate]) until the OWC monogram has had time to draw
/// its three letters. The session check used to finish in a blink, so the
/// router jumped straight past and the animation never got to play.
class SplashScreen extends StatefulWidget {
  const SplashScreen({Key? key}) : super(key: key);

  /// The monogram takes [markDuration] for a full cycle and has drawn all
  /// three letters by 62% of it (about 2 s); this holds a beat past that.
  static const markDuration = Duration(milliseconds: 3200);
  static const minimumDisplay = Duration(milliseconds: 2800);

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  late final SplashGate _gate;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    context.read<AuthBloc>().add(const AuthCheckRequested());
    _gate = context.read<SplashGate>();
    _timer = Timer(SplashScreen.minimumDisplay, _gate.complete);
  }

  @override
  void dispose() {
    _timer?.cancel();
    // However this screen goes, the router mustn't be left waiting on it.
    _gate.complete();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Stack(
        children: [
          Positioned(
            top: -90,
            left: -90,
            child: _glow(280, AppColors.primaryLight.withOpacity(0.16)),
          ),
          Positioned(
            bottom: -100,
            right: -80,
            child: _glow(260, const Color(0xFF2EE7FF).withOpacity(0.12)),
          ),
          SafeArea(
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const OwcMark(size: 116, duration: SplashScreen.markDuration),
                  const SizedBox(height: 24),
                  Text(
                    'OWNERCONNECT',
                    style: TextStyle(
                      fontFamily: 'SpaceGrotesk',
                      fontSize: 27,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 6,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    loc.translate('splash_tagline'),
                    style: const TextStyle(fontSize: 14, color: AppColors.textSecondary, fontWeight: FontWeight.w500),
                  ),
                  const SizedBox(height: 64),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: List.generate(3, (i) => _dot(i)),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    loc.translate('splash_checking'),
                    style: const TextStyle(fontSize: 12, color: AppColors.textTertiary),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _glow(double size, Color color) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(shape: BoxShape.circle, color: color, boxShadow: [
        BoxShadow(color: color, blurRadius: 90, spreadRadius: 40),
      ]),
    );
  }

  Widget _dot(int index) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.25, end: 1),
      duration: Duration(milliseconds: 700 + index * 120),
      curve: Curves.easeInOut,
      builder: (context, value, _) => Container(
        margin: const EdgeInsets.symmetric(horizontal: 3.5),
        width: 6,
        height: 6,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: AppColors.primary.withOpacity(value),
        ),
      ),
    );
  }
}
