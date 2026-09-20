import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/utils/file_download.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../data/models/clearance_model.dart';
import '../bloc/clearance_bloc.dart';
import '../bloc/clearance_event.dart';
import '../bloc/clearance_state.dart';
import '../../../../core/widgets/app_loading_indicator.dart';

class ClearanceScreen extends StatefulWidget {
  const ClearanceScreen({Key? key}) : super(key: key);

  @override
  State<ClearanceScreen> createState() => _ClearanceScreenState();
}

class _ClearanceScreenState extends State<ClearanceScreen> {
  List<Map<String, dynamic>> _units = [];
  int? _selectedUnitId;
  DateTime? _asOfDate;
  bool _isLoadingUnits = true;

  @override
  void initState() {
    super.initState();
    _loadUnits();
  }

  Future<void> _loadUnits() async {
    try {
      // Same profile-fetch used by ContactUsScreen for its unit picker —
      // /api/me/ already lists every unit the user is OwnerUnit-linked to,
      // independent of whether that unit has any charges yet.
      final profile = await context.read<AuthBloc>().repository.fetchAndPersistProfile();
      final units = (profile['units'] as List?)?.cast<Map<String, dynamic>>() ?? [];
      if (!mounted) return;
      setState(() {
        _units = units;
        _selectedUnitId = units.isNotEmpty ? units.first['id'] as int : null;
        _isLoadingUnits = false;
      });
      if (_selectedUnitId != null) {
        context.read<ClearanceBloc>().add(FetchClearanceHistoryEvent(unitId: _selectedUnitId));
      }
    } catch (_) {
      if (mounted) setState(() => _isLoadingUnits = false);
    }
  }

  Future<void> _pickAsOfDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _asOfDate ?? now,
      firstDate: DateTime(now.year - 5),
      lastDate: now,
    );
    if (picked != null) {
      setState(() => _asOfDate = picked);
    }
  }

  void _generate() {
    if (_selectedUnitId == null) return;
    context.read<ClearanceBloc>().add(
          GenerateClearanceEvent(unitId: _selectedUnitId!, asOfDate: _asOfDate),
        );
  }

  Future<void> _openPdf(int statementId, String url) async {
    try {
      final bytes = await context.read<ClearanceBloc>().repository.downloadFile(url);
      final opened = await saveAndOpenFile(bytes, 'clearance-$statementId.pdf');
      if (!opened && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppLocalizations.of(context).translate('download_receipt')), backgroundColor: AppColors.error),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppLocalizations.of(context).translate('download_receipt')), backgroundColor: AppColors.error),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.translate('clearance_title'))),
      body: _isLoadingUnits
          ? const Center(child: AppLoadingIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_units.length > 1) ...[
                  DropdownButtonFormField<int>(
                    value: _selectedUnitId,
                    decoration: InputDecoration(
                      labelText: loc.translate('select_unit'),
                      border: const OutlineInputBorder(),
                    ),
                    items: _units
                        .map((u) => DropdownMenuItem<int>(
                              value: u['id'] as int,
                              child: Text(u['unit_key'] as String? ?? ''),
                            ))
                        .toList(),
                    onChanged: (value) {
                      setState(() => _selectedUnitId = value);
                      if (value != null) {
                        context.read<ClearanceBloc>().add(FetchClearanceHistoryEvent(unitId: value));
                      }
                    },
                  ),
                  const SizedBox(height: 16),
                ],
                OutlinedButton.icon(
                  onPressed: _pickAsOfDate,
                  icon: const Icon(Icons.calendar_month_outlined),
                  label: Text(
                    _asOfDate != null
                        ? '${loc.translate('as_of_date')}: ${_asOfDate!.toIso8601String().split('T').first}'
                        : loc.translate('as_of_date'),
                  ),
                ),
                const SizedBox(height: 16),
                BlocBuilder<ClearanceBloc, ClearanceState>(
                  builder: (context, state) {
                    final isLoading = state.generateStatus == ClearanceGenerateStatus.loading;
                    return SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: (_selectedUnitId == null || isLoading) ? null : _generate,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primary,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                        child: isLoading
                            ? const AppLoadingIndicator(size: 20, strokeWidth: 2)
                            : Text(
                                loc.translate('generate_clearance'),
                                style: const TextStyle(color: Colors.white, fontSize: 16),
                              ),
                      ),
                    );
                  },
                ),
                const SizedBox(height: 20),
                BlocBuilder<ClearanceBloc, ClearanceState>(
                  builder: (context, state) {
                    if (state.generateStatus == ClearanceGenerateStatus.error) {
                      return Text(state.generateError ?? '', style: const TextStyle(color: AppColors.error));
                    }
                    if (state.latestStatement != null) {
                      return _StatementCard(
                        statement: state.latestStatement!,
                        onDownload: (url) => _openPdf(state.latestStatement!.id, url),
                      );
                    }
                    return const SizedBox.shrink();
                  },
                ),
                const SizedBox(height: 24),
                Text(loc.translate('clearance_history'), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                BlocBuilder<ClearanceBloc, ClearanceState>(
                  builder: (context, state) {
                    if (state.historyStatus == ClearanceHistoryStatus.loading) {
                      return const Padding(
                        padding: EdgeInsets.all(16),
                        child: Center(child: AppLoadingIndicator()),
                      );
                    }
                    if (state.history.isEmpty) {
                      return Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(loc.translate('no_clearance_yet'), style: const TextStyle(color: AppColors.textSecondary)),
                      );
                    }
                    return Column(
                      children: state.history
                          .map((s) => _StatementCard(statement: s, onDownload: (url) => _openPdf(s.id, url), compact: true))
                          .toList(),
                    );
                  },
                ),
              ],
            ),
    );
  }
}

class _StatementCard extends StatelessWidget {
  final ClearanceStatementModel statement;
  final void Function(String url) onDownload;
  final bool compact;

  const _StatementCard({required this.statement, required this.onDownload, this.compact = false});

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final statusColor = statement.isClear ? AppColors.success : AppColors.warning;
    final statusLabel = statement.isClear
        ? loc.translate('clearance_clear_status')
        : '${loc.translate('clearance_outstanding_status')}: ${statement.totalRemaining.toStringAsFixed(2)} EGP';

    return Card(
      margin: EdgeInsets.symmetric(vertical: compact ? 4 : 0, horizontal: 0),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(color: statusColor, borderRadius: BorderRadius.circular(8)),
              child: Text(statusLabel, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            ),
            const SizedBox(height: 12),
            Text('${loc.translate('unit')}: ${statement.unitKey}', style: const TextStyle(fontSize: 13)),
            Text(
              '${loc.translate('as_of_date')}: ${statement.asOfDate.toIso8601String().split('T').first}',
              style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            if (statement.pdfUrl != null) ...[
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () => onDownload(statement.pdfUrl!),
                  icon: const Icon(Icons.download, size: 18),
                  label: Text(loc.translate('download_receipt')),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
