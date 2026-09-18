import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';

/// Honest "coming soon" — there is no saved-card/tokenization concept in the
/// backend yet, and online payment itself is still blocked on real Paymob
/// merchant credentials. Showing a form here that can't actually save
/// anything would be worse than telling the truth.
class PaymentMethodsScreen extends StatelessWidget {
  const PaymentMethodsScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('payment_methods_title'))),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.credit_card_outlined, size: 48, color: AppColors.textSecondary),
              const SizedBox(height: 16),
              Text(
                loc.translate('payment_methods_coming_soon'),
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
