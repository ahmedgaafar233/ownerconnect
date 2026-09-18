import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../support/presentation/bloc/support_bloc.dart';
import '../../../support/presentation/bloc/support_event.dart';
import '../../../support/presentation/bloc/support_state.dart';

/// Reuses the already-fully-wired Ticket(category=OTHER) creation path
/// (SupportBloc/CreateTicketEvent) — same mechanism PaymentOptionsScreen's
/// "pay at office" option reuses — instead of a dead static contact page,
/// since Resort has no contact-info fields to show.
class ContactUsScreen extends StatefulWidget {
  const ContactUsScreen({Key? key}) : super(key: key);

  @override
  State<ContactUsScreen> createState() => _ContactUsScreenState();
}

class _ContactUsScreenState extends State<ContactUsScreen> {
  final _subjectController = TextEditingController();
  final _messageController = TextEditingController();
  int? _unitId;
  bool _isLoadingUnit = true;

  @override
  void initState() {
    super.initState();
    _loadUnit();
  }

  @override
  void dispose() {
    _subjectController.dispose();
    _messageController.dispose();
    super.dispose();
  }

  Future<void> _loadUnit() async {
    try {
      final profile = await context.read<AuthBloc>().repository.fetchAndPersistProfile();
      final units = profile['units'] as List?;
      if (mounted) {
        setState(() {
          _unitId = units != null && units.isNotEmpty ? units.first['id'] as int : null;
          _isLoadingUnit = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _isLoadingUnit = false);
    }
  }

  void _submit(BuildContext context) {
    if (_unitId == null || _subjectController.text.trim().isEmpty || _messageController.text.trim().isEmpty) {
      return;
    }
    context.read<SupportBloc>().add(
          CreateTicketEvent(
            unitId: _unitId!,
            category: 'OTHER',
            priority: 'MEDIUM',
            subject: _subjectController.text.trim(),
            description: _messageController.text.trim(),
          ),
        );
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('contact_us_title'))),
      body: BlocConsumer<SupportBloc, SupportState>(
        listener: (context, state) {
          if (state is TicketCreatedState) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(loc.translate('contact_us_sent'))),
            );
            Navigator.of(context).pop();
          } else if (state is SupportErrorState) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(state.message), backgroundColor: AppColors.error),
            );
          }
        },
        builder: (context, state) {
          final isSending = state is SupportLoadingState;

          if (_isLoadingUnit) {
            return const Center(child: CircularProgressIndicator());
          }
          if (_unitId == null) {
            return Center(child: Text(loc.translate('contact_us_no_unit')));
          }

          return Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  controller: _subjectController,
                  decoration: InputDecoration(labelText: loc.translate('contact_us_subject_hint')),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _messageController,
                  maxLines: 5,
                  decoration: InputDecoration(labelText: loc.translate('contact_us_message_hint')),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: isSending ? null : () => _submit(context),
                  child: isSending
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                        )
                      : Text(loc.translate('submit_request')),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
