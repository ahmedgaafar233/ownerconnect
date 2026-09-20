import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../bloc/financial_bloc.dart';
import '../bloc/financial_event.dart';
import '../../../../core/widgets/app_loading_indicator.dart';

class PaymentCheckoutScreen extends StatefulWidget {
  final String checkoutUrl;
  final String merchantOrderId;

  const PaymentCheckoutScreen({
    Key? key,
    required this.checkoutUrl,
    required this.merchantOrderId,
  }) : super(key: key);

  @override
  State<PaymentCheckoutScreen> createState() => _PaymentCheckoutScreenState();
}

class _PaymentCheckoutScreenState extends State<PaymentCheckoutScreen> {
  late final WebViewController _controller;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.white)
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageStarted: (String url) {
            setState(() {
              _isLoading = true;
            });
          },
          onPageFinished: (String url) {
            setState(() {
              _isLoading = false;
            });
          },
          onNavigationRequest: (NavigationRequest request) {
            final uri = Uri.parse(request.url);

            // Intercept Paymob callback redirect parameters
            final successParam = uri.queryParameters['success'];
            final isSuccess = successParam == 'true' || uri.queryParameters['pending'] == 'false' && successParam == 'true';
            final isFailed = successParam == 'false' || uri.queryParameters['error_occured'] == 'true';

            if (isSuccess) {
              _handlePaymentSuccess();
              return NavigationDecision.prevent;
            } else if (isFailed) {
              _handlePaymentFailure('Payment was cancelled or declined.');
              return NavigationDecision.prevent;
            }

            return NavigationDecision.navigate;
          },
        ),
      )
      ..loadRequest(Uri.parse(widget.checkoutUrl));
  }

  void _handlePaymentSuccess() {
    final loc = AppLocalizations.of(context);
    context.read<FinancialBloc>().add(
      PaymentCompletedEvent(receiptNo: widget.merchantOrderId),
    );

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            const Icon(Icons.check_circle, color: AppColors.success, size: 28),
            const SizedBox(width: 8),
            Text(loc.translate('payment_successful')),
          ],
        ),
        content: Text('${loc.translate('order_id')}: ${widget.merchantOrderId}\n${loc.translate('payment_processed_success')}'),
        actions: [
          ElevatedButton(
            onPressed: () {
              Navigator.of(context).pop(); // pop dialog
              Navigator.of(context).pop(); // pop checkout screen
            },
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _handlePaymentFailure(String message) {
    final loc = AppLocalizations.of(context);
    context.read<FinancialBloc>().add(
      PaymentFailedEvent(errorMessage: message),
    );

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('${loc.translate('payment_failed')}: $message'),
        backgroundColor: AppColors.error,
      ),
    );
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.translate('checkout_title')),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () {
            // A manual close never goes through onNavigationRequest's
            // success/fail redirect interception, so nothing else restores
            // ChargesScreen's list underneath — without this it's left
            // stuck on PaymentInitiatedState and renders blank.
            context.read<FinancialBloc>().add(const FetchChargesEvent(page: 1));
            Navigator.of(context).pop();
          },
        ),
      ),
      body: Stack(
        children: [
          WebViewWidget(controller: _controller),
          if (_isLoading)
            const Center(
              child: AppLoadingIndicator(),
            ),
        ],
      ),
    );
  }
}
