import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl_phone_field/intl_phone_field.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/utils/phone_utils.dart';
import '../../../../core/widgets/app_loading_indicator.dart';
import '../../../../core/widgets/owc_mark.dart';
import '../bloc/auth_bloc.dart';
import '../bloc/auth_event.dart';
import '../bloc/auth_state.dart';
import 'email_auth_screen.dart';

class PhoneEntryScreen extends StatefulWidget {
  const PhoneEntryScreen({Key? key}) : super(key: key);

  @override
  State<PhoneEntryScreen> createState() => _PhoneEntryScreenState();
}

class _PhoneEntryScreenState extends State<PhoneEntryScreen> {
  String? _fullPhoneNumber;
  bool _isValid = false;

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Stack(
        children: [
          Positioned(
            top: -110,
            right: -90,
            child: _glow(260, AppColors.primary.withOpacity(0.12)),
          ),
          Positioned(
            bottom: -90,
            left: -80,
            child: _glow(220, AppColors.primaryLight.withOpacity(0.08)),
          ),
          SafeArea(
            child: BlocConsumer<AuthBloc, AuthState>(
              listener: (context, state) {
                if (state is AuthErrorState) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(state.errorMessage), backgroundColor: AppColors.error),
                  );
                }
              },
              builder: (context, state) {
                final isLoading = state is AuthLoadingState;

                return SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 28),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const OwcMark(size: 56, animate: false),
                      const SizedBox(height: 24),

                      // Heading
                      Text(
                        loc.translate('login_title'),
                        style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        loc.translate('login_subtitle'),
                        style: const TextStyle(fontSize: 13.5, color: AppColors.textSecondary, height: 1.6),
                      ),
                      const SizedBox(height: 28),

                      // PRIMARY: phone entry — the real village-linked identity path
                      IntlPhoneField(
                        style: const TextStyle(color: AppColors.textPrimary, fontFamily: 'SpaceGrotesk'),
                        dropdownTextStyle: const TextStyle(color: AppColors.textPrimary),
                        decoration: InputDecoration(
                          labelText: loc.translate('phone_hint'),
                          counterText: '',
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(16)),
                        ),
                        initialCountryCode: 'EG',
                        onChanged: (phone) {
                          // isValidNumber() throws (not just returns false) while
                          // the number is still incomplete mid-typing — confirmed
                          // on a real device, every keystroke before the number
                          // was long enough crashed the app.
                          bool isValid;
                          try {
                            isValid = phone.isValidNumber();
                          } catch (_) {
                            isValid = false;
                          }
                          setState(() {
                            _fullPhoneNumber = normalizedCompleteNumber(phone);
                            _isValid = isValid;
                          });
                        },
                      ),
                      const SizedBox(height: 20),
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton(
                          onPressed: isLoading || !_isValid
                              ? null
                              : () {
                                  context.read<AuthBloc>().add(PhoneSubmitted(phone: _fullPhoneNumber!));
                                },
                          child: isLoading
                              ? const AppLoadingIndicator(size: 20, strokeWidth: 2)
                              : Text(loc.translate('continue_button')),
                        ),
                      ),

                      // Secondary, de-emphasized: Google / Email — below the
                      // real village-linked path, not competing above it.
                      const SizedBox(height: 28),
                      Row(
                        children: [
                          const Expanded(child: Divider()),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            child: Text(
                              loc.translate('or_continue_another_way'),
                              style: const TextStyle(color: AppColors.textTertiary, fontSize: 12),
                            ),
                          ),
                          const Expanded(child: Divider()),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: isLoading
                                  ? null
                                  : () => context.read<AuthBloc>().add(const GoogleSignInRequested()),
                              icon: const Icon(Icons.g_mobiledata, size: 22, color: AppColors.textSecondary),
                              label: Text(loc.translate('continue_with_google'), style: const TextStyle(fontSize: 12.5)),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: isLoading
                                  ? null
                                  : () => Navigator.of(context).push(
                                        MaterialPageRoute(
                                          builder: (_) => BlocProvider.value(
                                            value: context.read<AuthBloc>(),
                                            child: const EmailAuthScreen(),
                                          ),
                                        ),
                                      ),
                              icon: const Icon(Icons.email_outlined, size: 18, color: AppColors.textSecondary),
                              label: Text(loc.translate('continue_with_email'), style: const TextStyle(fontSize: 12.5)),
                            ),
                          ),
                        ],
                      ),

                      if (kDebugMode) ...[
                        const SizedBox(height: 20),
                        Center(
                          child: TextButton(
                            onPressed: isLoading || _fullPhoneNumber == null
                                ? null
                                : () {
                                    context.read<AuthBloc>().add(DevBypassRequested(phone: _fullPhoneNumber!));
                                  },
                            child: Text(loc.translate('dev_bypass_button')),
                          ),
                        ),
                      ],
                    ],
                  ),
                );
              },
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
        BoxShadow(color: color, blurRadius: 90, spreadRadius: 30),
      ]),
    );
  }
}
