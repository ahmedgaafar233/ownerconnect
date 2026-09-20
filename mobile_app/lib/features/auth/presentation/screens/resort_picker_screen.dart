import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../../core/widgets/app_loading_indicator.dart';
import '../../data/models/resort_model.dart';
import '../../data/repositories/resort_repository.dart';
import '../../data/resort_selection.dart';

/// First-launch, pre-login step: pick which resort's app this is. Purely
/// local branding state (see ResortSelection) — feeds the welcome screen
/// right after, never the actual tenant lock (AuthBloc/TenantMiddleware own
/// that, from the signed-in user's account).
class ResortPickerScreen extends StatefulWidget {
  const ResortPickerScreen({Key? key}) : super(key: key);

  @override
  State<ResortPickerScreen> createState() => _ResortPickerScreenState();
}

class _ResortPickerScreenState extends State<ResortPickerScreen> {
  late Future<List<ResortModel>> _future;
  String _query = '';

  @override
  void initState() {
    super.initState();
    _future = context.read<ResortRepository>().getResorts();
  }

  Future<void> _select(ResortModel resort) async {
    await context.read<ResortSelection>().select(resort);
    if (mounted) context.go('/welcome-resort');
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 24, 24, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    loc.translate('select_resort_title'),
                    style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    loc.translate('select_resort_subtitle'),
                    style: const TextStyle(fontSize: 14, color: AppColors.textSecondary),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              child: TextField(
                onChanged: (value) => setState(() => _query = value.trim().toLowerCase()),
                decoration: InputDecoration(
                  hintText: loc.translate('search_resort_hint'),
                  prefixIcon: const Icon(Icons.search, color: AppColors.textTertiary),
                  filled: true,
                  fillColor: AppColors.surface,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(14),
                    borderSide: const BorderSide(color: AppColors.border),
                  ),
                ),
              ),
            ),
            Expanded(
              child: FutureBuilder<List<ResortModel>>(
                future: _future,
                builder: (context, snapshot) {
                  if (snapshot.connectionState != ConnectionState.done) {
                    return const Center(child: AppLoadingIndicator());
                  }
                  if (snapshot.hasError) {
                    return Center(
                      child: TextButton(
                        onPressed: () => setState(() => _future = context.read<ResortRepository>().getResorts()),
                        child: Text(loc.translate('retry')),
                      ),
                    );
                  }
                  final resorts = (snapshot.data ?? [])
                      .where((r) => _query.isEmpty || r.name.toLowerCase().contains(_query))
                      .toList();
                  if (resorts.isEmpty) {
                    return Center(
                      child: Text(loc.translate('no_resorts_found'), style: const TextStyle(color: AppColors.textSecondary)),
                    );
                  }
                  return ListView.separated(
                    padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
                    itemCount: resorts.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 10),
                    itemBuilder: (context, index) {
                      final resort = resorts[index];
                      return _ResortTile(resort: resort, onTap: () => _select(resort));
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResortTile extends StatelessWidget {
  final ResortModel resort;
  final VoidCallback onTap;

  const _ResortTile({required this.resort, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border),
          ),
          child: Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: SizedBox(
                  width: 48,
                  height: 48,
                  child: resort.logoUrl != null
                      ? Image.network(
                          resort.logoUrl!,
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) => const _ResortIconFallback(),
                        )
                      : const _ResortIconFallback(),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Text(
                  resort.name,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: AppColors.textPrimary),
                ),
              ),
              const Icon(Icons.chevron_right, color: AppColors.textTertiary),
            ],
          ),
        ),
      ),
    );
  }
}

class _ResortIconFallback extends StatelessWidget {
  const _ResortIconFallback();

  @override
  Widget build(BuildContext context) {
    return const DecoratedBox(
      decoration: BoxDecoration(gradient: AppColors.primaryGradient),
      child: Icon(Icons.villa_outlined, color: Colors.white, size: 24),
    );
  }
}
