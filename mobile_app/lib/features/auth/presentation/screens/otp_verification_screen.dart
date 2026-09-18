import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../bloc/auth_bloc.dart';
import '../bloc/auth_event.dart';
import '../bloc/auth_state.dart';
import '../widgets/otp_box_field.dart';

class OtpVerificationScreen extends StatefulWidget {
  const OtpVerificationScreen({Key? key}) : super(key: key);

  @override
  State<OtpVerificationScreen> createState() => _OtpVerificationScreenState();
}

class _OtpVerificationScreenState extends State<OtpVerificationScreen> {
  static const _resendCooldown = 60;
  int _secondsLeft = _resendCooldown;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _startCooldown();
  }

  void _startCooldown() {
    _secondsLeft = _resendCooldown;
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_secondsLeft == 0) {
        timer.cancel();
      } else {
        setState(() => _secondsLeft--);
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('otp_title'))),
      body: SafeArea(
        child: BlocConsumer<AuthBloc, AuthState>(
          listener: (context, state) {
            if (state is AuthErrorState) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text(state.errorMessage), backgroundColor: AppColors.error),
              );
            }
          },
          builder: (context, state) {
            final otpState = state is OtpSentState ? state : null;
            final isLoading = state is AuthLoadingState;

            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${loc.translate('otp_subtitle')} ${otpState?.phone ?? ''}',
                    style: const TextStyle(fontSize: 14, color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 32),
                  OtpBoxField(
                    onCompleted: (code) {
                      context.read<AuthBloc>().add(OtpSubmitted(smsCode: code));
                    },
                  ),
                  const SizedBox(height: 24),
                  if (isLoading) const Center(child: CircularProgressIndicator()),
                  const SizedBox(height: 24),
                  Center(
                    child: _secondsLeft > 0
                        ? Text(
                            '${loc.translate('resend_in')} ${_secondsLeft}s',
                            style: const TextStyle(color: AppColors.textSecondary),
                          )
                        : TextButton(
                            onPressed: otpState == null
                                ? null
                                : () {
                                    context.read<AuthBloc>().add(PhoneSubmitted(phone: otpState.phone));
                                    _startCooldown();
                                  },
                            child: Text(loc.translate('resend_code')),
                          ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}
