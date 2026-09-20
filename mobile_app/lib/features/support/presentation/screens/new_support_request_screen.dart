import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/widgets/app_loading_indicator.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../bloc/support_bloc.dart';
import '../bloc/support_event.dart';
import '../bloc/support_state.dart';

class _IssueType {
  final String labelKey;
  final IconData icon;
  const _IssueType(this.labelKey, this.icon);
}

const _issueTypes = [
  _IssueType('category_electrician', Icons.electrical_services),
  _IssueType('category_plumber', Icons.plumbing),
  _IssueType('category_carpenter', Icons.carpenter),
  _IssueType('category_satellite', Icons.satellite_alt),
  _IssueType('category_gardening', Icons.grass),
  _IssueType('category_pest_control', Icons.pest_control),
];

/// Category on the backend stays MAINTENANCE for every issue type here —
/// the technician type the owner picks becomes the ticket's subject, not a
/// new backend enum value, so the existing Tenant restriction (category
/// must be MAINTENANCE) and staff workflows need no changes.
class NewSupportRequestScreen extends StatefulWidget {
  const NewSupportRequestScreen({Key? key}) : super(key: key);

  @override
  State<NewSupportRequestScreen> createState() => _NewSupportRequestScreenState();
}

class _NewSupportRequestScreenState extends State<NewSupportRequestScreen> {
  final _detailsController = TextEditingController();
  int? _unitId;
  bool _isLoadingUnit = true;
  bool _hasLoadError = false;
  String? _selectedTypeKey;

  @override
  void initState() {
    super.initState();
    _loadUnit();
  }

  @override
  void dispose() {
    _detailsController.dispose();
    super.dispose();
  }

  Future<void> _loadUnit() async {
    setState(() {
      _isLoadingUnit = true;
      _hasLoadError = false;
    });
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
      if (mounted) {
        setState(() {
          _isLoadingUnit = false;
          _hasLoadError = true;
        });
      }
    }
  }

  void _submit(BuildContext context) {
    if (_unitId == null || _selectedTypeKey == null) return;
    final loc = AppLocalizations.of(context);
    final subject = loc.translate(_selectedTypeKey!);
    context.read<SupportBloc>().add(
          CreateTicketEvent(
            unitId: _unitId!,
            category: 'MAINTENANCE',
            priority: 'MEDIUM',
            subject: subject,
            description: _detailsController.text.trim(),
          ),
        );
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('create_ticket'))),
      body: BlocConsumer<SupportBloc, SupportState>(
        listener: (context, state) {
          if (state is TicketCreatedState) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(loc.translate('ticket_submitted'))),
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
            return const Center(child: AppLoadingIndicator());
          }
          if (_hasLoadError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      loc.translate('load_unit_error'),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton(
                      onPressed: _loadUnit,
                      child: Text(loc.translate('retry_button')),
                    ),
                  ],
                ),
              ),
            );
          }
          if (_unitId == null) {
            return Center(child: Text(loc.translate('contact_us_no_unit')));
          }

          return SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  loc.translate('select_issue_type'),
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
                ),
                const SizedBox(height: 16),
                GridView.count(
                  crossAxisCount: 2,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  childAspectRatio: 1.35,
                  children: _issueTypes.map((type) {
                    final isSelected = _selectedTypeKey == type.labelKey;
                    return _IssueTypeCard(
                      label: loc.translate(type.labelKey),
                      icon: type.icon,
                      isSelected: isSelected,
                      onTap: () => setState(() => _selectedTypeKey = type.labelKey),
                    );
                  }).toList(),
                ),
                const SizedBox(height: 24),
                TextField(
                  controller: _detailsController,
                  maxLines: 4,
                  decoration: InputDecoration(labelText: loc.translate('issue_details_hint')),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: isSending || _selectedTypeKey == null ? null : () => _submit(context),
                  child: isSending
                      ? const AppLoadingIndicator(size: 20, strokeWidth: 2)
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

class _IssueTypeCard extends StatelessWidget {
  const _IssueTypeCard({
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: isSelected ? AppColors.glassFill : AppColors.cardBg,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        borderRadius: BorderRadius.circular(18),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: isSelected ? AppColors.primary : AppColors.border,
              width: isSelected ? 2 : 1,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: isSelected ? AppColors.primary : AppColors.textSecondary, size: 28),
              const SizedBox(height: 10),
              Text(
                label,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: isSelected ? AppColors.primary : AppColors.textPrimary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
