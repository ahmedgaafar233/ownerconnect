import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../data/models/visitor_pass_model.dart';
import '../bloc/visitor_pass_bloc.dart';
import '../bloc/visitor_pass_event.dart';
import '../bloc/visitor_pass_state.dart';
import '../widgets/pass_qr_dialog.dart';
import '../../../../core/widgets/app_loading_indicator.dart';
import '../../../profile/presentation/widgets/stay_card.dart';
import 'new_visitor_pass_screen.dart';

class VisitorPassesScreen extends StatefulWidget {
  const VisitorPassesScreen({Key? key}) : super(key: key);

  @override
  State<VisitorPassesScreen> createState() => _VisitorPassesScreenState();
}

class _VisitorPassesScreenState extends State<VisitorPassesScreen> {
  @override
  void initState() {
    super.initState();
    context.read<VisitorPassBloc>().add(const FetchVisitorPassesEvent(page: 1));
  }

  /// Creating a pass leaves the bloc in its "created" state, which this list
  /// can't render, so it reloads once the form closes.
  Future<void> _openCreateForm() async {
    await Navigator.of(context)
        .push(MaterialPageRoute(builder: (_) => const NewVisitorPassScreen()));
    if (!mounted) return;
    context.read<VisitorPassBloc>().add(const FetchVisitorPassesEvent(page: 1));
  }

  /// Pull-to-refresh: reload in place and wait for it, so the spinner ends
  /// when the new list is actually there.
  Future<void> _refresh() async {
    final bloc = context.read<VisitorPassBloc>();
    bloc.add(const FetchVisitorPassesEvent(refresh: true));
    await bloc.stream.firstWhere((s) => s is VisitorPassesLoadedState);
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'ACTIVE':
        return AppColors.success;
      case 'PENDING':
        return AppColors.warning;
      case 'REJECTED':
        return AppColors.error;
      default:
        return AppColors.textSecondary;
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.translate('passes_title')),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openCreateForm,
        backgroundColor: AppColors.primary,
        icon: const Icon(Icons.add),
        label: Text(loc.translate('create_pass')),
      ),
      body: Column(
        children: [
          // A long-term tenant's stay dates sit above their QR codes.
          const StayCard(),
          Expanded(
            child: BlocBuilder<VisitorPassBloc, VisitorPassState>(
        builder: (context, state) {
          if (state is VisitorPassLoadingState) {
            return const Center(child: AppLoadingIndicator());
          } else if (state is VisitorPassesLoadedState) {
            return RefreshIndicator(
              onRefresh: _refresh,
              child: state.passes.isEmpty
                  ? ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      children: [
                        SizedBox(
                          height: MediaQuery.of(context).size.height * 0.5,
                          child: Center(child: Text(loc.translate('no_passes'))),
                        ),
                      ],
                    )
                  : ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              itemCount: state.passes.length,
              itemBuilder: (context, index) {
                final pass = state.passes[index];
                final isActive = pass.status == 'ACTIVE';
                return Card(
                  margin:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: ListTile(
                    leading: Icon(
                      isActive ? Icons.qr_code_2 : Icons.hourglass_empty,
                      size: 36,
                      color:
                          isActive ? AppColors.primary : AppColors.textTertiary,
                    ),
                    title: Text(
                      pass.visitorName,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                            '${loc.translate(passTypeLabelKey(pass.passType))} • ${loc.translate('unit')} ${pass.unitKey}'),
                        const SizedBox(height: 4),
                        Text(
                          loc.translate(
                              'pass_status_${pass.status.toLowerCase()}'),
                          style: TextStyle(
                              fontWeight: FontWeight.w600,
                              color: _statusColor(pass.status)),
                        ),
                        if (pass.status == 'REJECTED' &&
                            pass.rejectionReason.isNotEmpty)
                          Text(pass.rejectionReason,
                              style: const TextStyle(
                                  color: AppColors.textSecondary)),
                      ],
                    ),
                    isThreeLine: true,
                    // A pass only works at the gate once it's active, so the
                    // QR is only offered then.
                    trailing: isActive
                        ? TextButton(
                            onPressed: () {
                              showDialog(
                                context: context,
                                builder: (_) => PassQrDialog(pass: pass),
                              );
                            },
                            child: Text(loc.translate('qr_code')),
                          )
                        : null,
                  ),
                );
              },
            ),
            );
          } else if (state is VisitorPassErrorState) {
            return Center(child: Text(state.message));
          }
          return const SizedBox.shrink();
        },
      ),
          ),
        ],
      ),
    );
  }
}
