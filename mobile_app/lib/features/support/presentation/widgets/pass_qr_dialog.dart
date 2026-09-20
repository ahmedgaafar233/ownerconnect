import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../data/models/visitor_pass_model.dart';

class PassQrDialog extends StatelessWidget {
  final VisitorPassModel pass;

  const PassQrDialog({Key? key, required this.pass}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Dialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              pass.passType,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.primary),
            ),
            const SizedBox(height: 8),
            Text(
              pass.visitorName,
              style: const TextStyle(fontSize: 16, color: AppColors.textPrimary),
            ),
            const SizedBox(height: 16),
            // A QR code must stay black-on-white regardless of the app's dark
            // theme — the security/recreation gate scanner needs maximum
            // contrast, not brand consistency.
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
              ),
              child: QrImageView(
                data: pass.passCode,
                version: QrVersions.auto,
                size: 200.0,
                backgroundColor: Colors.white,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              '${loc.translate('pass_code_label')}: ${pass.passCode}',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text(loc.translate('close_button')),
            ),
          ],
        ),
      ),
    );
  }
}
