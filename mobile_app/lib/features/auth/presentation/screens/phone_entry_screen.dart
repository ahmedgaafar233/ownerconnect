import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl_phone_field/intl_phone_field.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/utils/phone_utils.dart';
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
            final isLoading = state is AuthLoadingState;

            return SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    loc.translate('login_title'),
                    style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    loc.translate('login_subtitle'),
                    style: const TextStyle(fontSize: 14, color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 32),
                  OutlinedButton.icon(
                    onPressed: isLoading
                        ? null
                        : () => context.read<AuthBloc>().add(const GoogleSignInRequested()),
                    icon: const Icon(Icons.g_mobiledata, size: 28),
                    label: Text(loc.translate('continue_with_google')),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
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
                    icon: const Icon(Icons.email_outlined),
                    label: Text(loc.translate('continue_with_email')),
                  ),
                  const SizedBox(height: 24),
                  Row(
                    children: [
                      const Expanded(child: Divider()),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                        child: Text(loc.translate('or_divider'), style: const TextStyle(color: AppColors.textSecondary)),
                      ),
                      const Expanded(child: Divider()),
                    ],
                  ),
                  const SizedBox(height: 24),
                  IntlPhoneField(
                    decoration: InputDecoration(
                      labelText: loc.translate('phone_hint'),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
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
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: isLoading || !_isValid
                        ? null
                        : () {
                            context.read<AuthBloc>().add(PhoneSubmitted(phone: _fullPhoneNumber!));
                          },
                    child: isLoading
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                          )
                        : Text(loc.translate('continue_button')),
                  ),
                  if (kDebugMode) ...[
                    const SizedBox(height: 16),
                    OutlinedButton(
                      onPressed: isLoading || _fullPhoneNumber == null
                          ? null
                          : () {
                              context.read<AuthBloc>().add(DevBypassRequested(phone: _fullPhoneNumber!));
                            },
                      child: Text(loc.translate('dev_bypass_button')),
                    ),
                  ],
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}
