import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../data/models/payment_model.dart';
import '../bloc/financial_bloc.dart';
import '../bloc/financial_event.dart';
import '../bloc/financial_state.dart';
import '../widgets/month_filter_bar.dart';

class PaymentHistoryScreen extends StatefulWidget {
  const PaymentHistoryScreen({Key? key}) : super(key: key);

  @override
  State<PaymentHistoryScreen> createState() => _PaymentHistoryScreenState();
}

class _PaymentHistoryScreenState extends State<PaymentHistoryScreen> {
  final ScrollController _scrollController = ScrollController();
  int? _filterYear;
  int? _filterMonth;

  @override
  void initState() {
    super.initState();
    context.read<FinancialBloc>().add(const FetchPaymentHistoryEvent(page: 1));
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_isBottom) {
      final state = context.read<FinancialBloc>().state;
      if (state is PaymentHistoryLoadedState && !state.hasReachedMax && !state.isFetchingMore) {
        context.read<FinancialBloc>().add(FetchPaymentHistoryEvent(
              page: state.currentPage + 1,
              year: _filterYear,
              month: _filterMonth,
            ));
      }
    }
  }

  void _onMonthFilterChanged(DateTime? picked) {
    setState(() {
      _filterYear = picked?.year;
      _filterMonth = picked?.month;
    });
    context.read<FinancialBloc>().add(FetchPaymentHistoryEvent(page: 1, year: _filterYear, month: _filterMonth));
  }

  bool get _isBottom {
    if (!_scrollController.hasClients) return false;
    final maxScroll = _scrollController.position.maxScrollExtent;
    final currentScroll = _scrollController.offset;
    return currentScroll >= (maxScroll * 0.9);
  }

  Future<void> _openReceipt(String url) async {
    final uri = Uri.parse(url);
    final launched = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!launched && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(AppLocalizations.of(context).translate('download_receipt')), backgroundColor: AppColors.error),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.translate('payment_history_title')),
        actions: [
          MonthFilterBar(year: _filterYear, month: _filterMonth, onChanged: _onMonthFilterChanged),
        ],
      ),
      body: BlocBuilder<FinancialBloc, FinancialState>(
        builder: (context, state) {
          if (state is FinancialLoadingState) {
            return const Center(child: CircularProgressIndicator());
          } else if (state is PaymentHistoryLoadedState) {
            if (state.payments.isEmpty) {
              return Center(child: Text(loc.translate('no_payments_yet')));
            }
            return ListView.builder(
              controller: _scrollController,
              itemCount: state.hasReachedMax ? state.payments.length : state.payments.length + 1,
              itemBuilder: (context, index) {
                if (index >= state.payments.length) {
                  return const Padding(
                    padding: EdgeInsets.all(16.0),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                return _PaymentTile(
                  payment: state.payments[index],
                  onDownload: _openReceipt,
                );
              },
            );
          } else if (state is FinancialErrorState) {
            return Center(child: Text(state.errorMessage));
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}

class _PaymentTile extends StatelessWidget {
  final PaymentModel payment;
  final void Function(String url) onDownload;

  const _PaymentTile({required this.payment, required this.onDownload});

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: ListTile(
        contentPadding: const EdgeInsets.all(16),
        title: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              '${payment.totalAmount.toStringAsFixed(2)} EGP',
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: AppColors.primary),
            ),
            Text(
              payment.paidAt.isNotEmpty ? payment.paidAt.split('T').first : '',
              style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
            ),
          ],
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 8),
            Text(
              '${loc.translate('unit')}: ${payment.unitKey}',
              style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            Text(
              '${loc.translate('receipt_no_label')}: ${payment.receiptNo}',
              style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
          ],
        ),
        trailing: payment.receiptPdfUrl != null
            ? IconButton(
                icon: const Icon(Icons.download, color: AppColors.secondary),
                tooltip: loc.translate('download_receipt'),
                onPressed: () => onDownload(payment.receiptPdfUrl!),
              )
            : null,
      ),
    );
  }
}
