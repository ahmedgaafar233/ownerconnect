import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../bloc/support_bloc.dart';
import '../bloc/support_event.dart';
import '../bloc/support_state.dart';
import '../widgets/pass_qr_dialog.dart';
import '../../../../core/widgets/app_loading_indicator.dart';

class VisitorPassesScreen extends StatefulWidget {
  const VisitorPassesScreen({Key? key}) : super(key: key);

  @override
  State<VisitorPassesScreen> createState() => _VisitorPassesScreenState();
}

class _VisitorPassesScreenState extends State<VisitorPassesScreen> {
  @override
  void initState() {
    super.initState();
    context.read<SupportBloc>().add(const FetchVisitorPassesEvent(page: 1));
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.translate('passes_title')),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          // Open Pass Creation
        },
        backgroundColor: AppColors.primary,
        icon: const Icon(Icons.add),
        label: Text(loc.translate('create_pass')),
      ),
      body: BlocBuilder<SupportBloc, SupportState>(
        builder: (context, state) {
          if (state is SupportLoadingState) {
            return const Center(child: AppLoadingIndicator());
          } else if (state is VisitorPassesLoadedState) {
            if (state.passes.isEmpty) {
              return Center(child: Text(loc.translate('no_passes')));
            }
            return ListView.builder(
              itemCount: state.passes.length,
              itemBuilder: (context, index) {
                final pass = state.passes[index];
                return Card(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: ListTile(
                    leading: const Icon(Icons.qr_code_2, size: 36, color: AppColors.primary),
                    title: Text(
                      pass.visitorName,
                      style: const TextStyle(fontWeight: FontWeight.bold),
                    ),
                    subtitle: Text('${pass.passType} • Unit ${pass.unitKey}'),
                    trailing: TextButton(
                      onPressed: () {
                        showDialog(
                          context: context,
                          builder: (_) => PassQrDialog(pass: pass),
                        );
                      },
                      child: Text(loc.translate('qr_code')),
                    ),
                  ),
                );
              },
            );
          } else if (state is SupportErrorState) {
            return Center(child: Text(state.message));
          }
          return const SizedBox.shrink();
        },
      ),
    );
  }
}
