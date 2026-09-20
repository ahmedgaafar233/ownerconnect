import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../bloc/financial_bloc.dart';
import '../bloc/financial_event.dart';
import '../bloc/financial_state.dart';
import '../../../support/presentation/bloc/support_bloc.dart';
import '../widgets/charge_card.dart';
import '../widgets/charge_summary_card.dart';
import '../widgets/month_filter_bar.dart';
import 'payment_options_screen.dart';
import '../../../../core/widgets/app_loading_indicator.dart';

class ChargesScreen extends StatefulWidget {
  const ChargesScreen({Key? key}) : super(key: key);

  @override
  State<ChargesScreen> createState() => _ChargesScreenState();
}

class _ChargesScreenState extends State<ChargesScreen> {
  final List<int> _selectedChargeIds = [];
  final ScrollController _scrollController = ScrollController();
  int? _filterYear;
  int? _filterMonth;

  @override
  void initState() {
    super.initState();
    context.read<FinancialBloc>().add(const FetchChargesEvent(page: 1));
    context.read<FinancialBloc>().add(const FetchChargeSummaryEvent());
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
      if (state is ChargesLoadedState && !state.hasReachedMax && !state.isFetchingMore) {
        context.read<FinancialBloc>().add(FetchChargesEvent(
              page: state.currentPage + 1,
              year: _filterYear,
              month: _filterMonth,
            ));
      }
    }
  }

  bool get _isBottom {
    if (!_scrollController.hasClients) return false;
    final maxScroll = _scrollController.position.maxScrollExtent;
    final currentScroll = _scrollController.offset;
    return currentScroll >= (maxScroll * 0.9);
  }

  void _onMonthFilterChanged(DateTime? picked) {
    setState(() {
      _filterYear = picked?.year;
      _filterMonth = picked?.month;
    });
    context.read<FinancialBloc>().add(FetchChargesEvent(page: 1, year: _filterYear, month: _filterMonth));
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.translate('charges_title')),
        actions: [
          MonthFilterBar(year: _filterYear, month: _filterMonth, onChanged: _onMonthFilterChanged),
        ],
      ),
      body: BlocConsumer<FinancialBloc, FinancialState>(
        listener: (context, state) {
          if (state is FinancialErrorState) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.errorMessage), backgroundColor: AppColors.error),
            );
          }
        },
        builder: (context, state) {
          if (state is FinancialLoadingState) {
            return const Center(child: AppLoadingIndicator());
          } else if (state is ChargesLoadedState) {
            if (state.charges.isEmpty) {
              return Column(
                children: [
                  if (state.summary != null) ChargeSummaryCard(summary: state.summary!),
                  Expanded(child: Center(child: Text(loc.translate('no_charges')))),
                ],
              );
            }
            return Column(
              children: [
                if (state.summary != null) ChargeSummaryCard(summary: state.summary!),
                Expanded(
                  child: ListView.builder(
                    controller: _scrollController,
                    itemCount: state.hasReachedMax
                        ? state.charges.length
                        : state.charges.length + 1,
                    itemBuilder: (context, index) {
                      if (index >= state.charges.length) {
                        return const Padding(
                          padding: EdgeInsets.all(16.0),
                          child: Center(child: AppLoadingIndicator()),
                        );
                      }
                      final charge = state.charges[index];
                      final isSelected = _selectedChargeIds.contains(charge.id);
                      return ChargeCard(
                        charge: charge,
                        isSelected: isSelected,
                        onSelect: (val) {
                          setState(() {
                            if (val == true) {
                              _selectedChargeIds.add(charge.id);
                            } else {
                              _selectedChargeIds.remove(charge.id);
                            }
                          });
                        },
                      );
                    },
                  ),
                ),
                if (_selectedChargeIds.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Theme.of(context).cardColor,
                      boxShadow: [
                        BoxShadow(
                          color: AppColors.primary.withOpacity(0.1),
                          blurRadius: 10,
                        )
                      ],
                    ),
                    child: SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primary,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                        onPressed: () {
                          final selectedCharges =
                              state.charges.where((c) => _selectedChargeIds.contains(c.id)).toList();
                          Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => MultiBlocProvider(
                                providers: [
                                  BlocProvider.value(value: context.read<FinancialBloc>()),
                                  BlocProvider.value(value: context.read<SupportBloc>()),
                                ],
                                child: PaymentOptionsScreen(selectedCharges: selectedCharges),
                              ),
                            ),
                          );
                        },
                        child: Text('${loc.translate('pay_now')} (${_selectedChargeIds.length})'),
                      ),
                    ),
                  ),
              ],
            );
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}
