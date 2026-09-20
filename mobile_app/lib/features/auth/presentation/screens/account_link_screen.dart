import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl_phone_field/intl_phone_field.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/utils/phone_utils.dart';
import '../bloc/auth_bloc.dart';
import '../bloc/auth_event.dart';
import '../bloc/auth_state.dart';
import '../widgets/otp_box_field.dart';
import '../../../../core/widgets/app_loading_indicator.dart';

/// Shown right after a Google/Email sign-in the backend doesn't recognize
/// yet (AccountLinkRequiredState) — collects the phone number staff already
/// has on file plus the activation code they gave the owner, and submits
/// both together to link this Firebase identity to that pre-provisioned
/// owner record (see FirebaseAuthView's account-link branch).
class AccountLinkScreen extends StatefulWidget {
  const AccountLinkScreen({Key? key}) : super(key: key);

  @override
  State<AccountLinkScreen> createState() => _AccountLinkScreenState();
}

class _AccountLinkScreenState extends State<AccountLinkScreen> {
  String? _phone;
  String _code = '';

  void _submit(BuildContext context) {
    if (_phone == null || _code.length != 6) return;
    context.read<AuthBloc>().add(AccountLinkSubmitted(phone: _phone!, code: _code));
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('link_account_title'))),
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

            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    loc.translate('link_account_subtitle'),
                    style: const TextStyle(fontSize: 14, color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 24),
                  IntlPhoneField(
                    decoration: InputDecoration(
                      labelText: loc.translate('phone_hint'),
                      counterText: '',
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    initialCountryCode: 'EG',
                    onChanged: (phone) => setState(() => _phone = normalizedCompleteNumber(phone)),
                  ),
                  const SizedBox(height: 24),
                  Text(loc.translate('activation_code_hint'), style: const TextStyle(color: AppColors.textSecondary)),
                  const SizedBox(height: 8),
                  OtpBoxField(onCompleted: (code) => setState(() => _code = code)),
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: isLoading || _phone == null || _code.length != 6 ? null : () => _submit(context),
                    child: isLoading
                        ? const AppLoadingIndicator(size: 20, strokeWidth: 2)
                        : Text(loc.translate('continue_button')),
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
