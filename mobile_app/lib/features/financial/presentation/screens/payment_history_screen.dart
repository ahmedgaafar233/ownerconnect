import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/widgets/app_loading_indicator.dart';
import '../../../../core/widgets/pdf_viewer_screen.dart';
import '../../data/models/payment_model.dart';
import '../bloc/financial_bloc.dart';
import '../bloc/payment_history_bloc.dart';
import '../bloc/payment_history_event.dart';
import '../bloc/payment_history_state.dart';
import '../widgets/month_filter_bar.dart';

/// Owns its own [PaymentHistoryBloc] for as long as the screen is open — see
/// that class for why it must not share [FinancialBloc] with the charges page.
class PaymentHistoryScreen extends StatelessWidget {
  const PaymentHistoryScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    // Resolved eagerly: BlocProvider.create is lazy, and a closure reading
    // this context later can hit an already-deactivated widget (the same
    // crash the drawer's clearance entry used to have).
    final repository = context.read<FinancialBloc>().repository;
    return BlocProvider(
      create: (_) => PaymentHistoryBloc(repository: repository),
      child: const _PaymentHistoryView(),
    );
  }
}

class _PaymentHistoryView extends StatefulWidget {
  const _PaymentHistoryView();

  @override
  State<_PaymentHistoryView> createState() => _PaymentHistoryViewState();
}

class _PaymentHistoryViewState extends State<_PaymentHistoryView> {
  final ScrollController _scrollController = ScrollController();
  int? _filterYear;
  int? _filterMonth;

  @override
  void initState() {
    super.initState();
    context.read<PaymentHistoryBloc>().add(const FetchPaymentHistoryEvent(page: 1));
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
      final state = context.read<PaymentHistoryBloc>().state;
      if (state is PaymentHistoryLoadedState && !state.hasReachedMax && !state.isFetchingMore) {
        context.read<PaymentHistoryBloc>().add(FetchPaymentHistoryEvent(
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
    context.read<PaymentHistoryBloc>().add(FetchPaymentHistoryEvent(page: 1, year: _filterYear, month: _filterMonth));
  }

  bool get _isBottom {
    if (!_scrollController.hasClients) return false;
    final maxScroll = _scrollController.position.maxScrollExtent;
    final currentScroll = _scrollController.offset;
    return currentScroll >= (maxScroll * 0.9);
  }

  /// Opens the receipt inside the app — read first, keep a copy if wanted.
  void _viewReceipt(PaymentModel payment, String url) {
    final repository = context.read<PaymentHistoryBloc>().repository;
    final loc = AppLocalizations.of(context);
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => PdfViewerScreen(
        title: '${loc.translate('receipt_no_label')} ${payment.receiptNo}',
        fileName: 'receipt-${payment.id}',
        loadBytes: () => repository.downloadFile(url),
      ),
    ));
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
      body: BlocBuilder<PaymentHistoryBloc, PaymentHistoryState>(
        builder: (context, state) {
          if (state is PaymentHistoryLoadingState) {
            return const Center(child: AppLoadingIndicator());
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
                    child: Center(child: AppLoadingIndicator()),
                  );
                }
                return _PaymentTile(
                  payment: state.payments[index],
                  onView: (url) => _viewReceipt(state.payments[index], url),
                );
              },
            );
          } else if (state is PaymentHistoryErrorState) {
            return Center(child: Text(state.message));
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}

class _PaymentTile extends StatelessWidget {
  final PaymentModel payment;
  final void Function(String url) onView;

  const _PaymentTile({required this.payment, required this.onView});

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: ListTile(
        contentPadding: const EdgeInsets.all(16),
        onTap: payment.receiptPdfUrl != null ? () => onView(payment.receiptPdfUrl!) : null,
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
                icon: const Icon(Icons.receipt_long_rounded, color: AppColors.secondary),
                tooltip: loc.translate('view_receipt'),
                onPressed: () => onView(payment.receiptPdfUrl!),
              )
            : null,
      ),
    );
  }
}
