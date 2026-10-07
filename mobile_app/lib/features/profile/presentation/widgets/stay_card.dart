import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../auth/presentation/bloc/auth_state.dart';
import 'meter_readings_card.dart';
import 'unit_labels.dart';

/// What a long-term tenant most needs on their pass screen: when their stay
/// starts and ends, and a reminder that the QR codes below open the village
/// gate and the pool. Shows nothing for anyone who isn't a tenant.
class StayCard extends StatelessWidget {
  const StayCard({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AuthBloc>().state;
    if (state is! AuthenticatedState || state.role != 'TENANT') return const SizedBox.shrink();

    final stays = state.units.where((unit) => unit.lease != null).toList();
    if (stays.isEmpty) return const SizedBox.shrink();

    final loc = AppLocalizations.of(context);
    return Column(
      children: [
        for (final unit in stays)
          Container(
            width: double.infinity,
            margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: AppColors.primaryGradient,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${loc.translate('stay_title')} · ${unit.unitKey}',
                  style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 6),
                Text(
                  fillIn(loc.translate('tenant_lease_line'), [
                    formatServerDate(context, unit.lease!.startDate),
                    formatServerDate(context, unit.lease!.endDate),
                  ]),
                  style: const TextStyle(color: Colors.white),
                ),
                const SizedBox(height: 4),
                Text(
                  loc.translate(unit.lease!.isEnded ? 'tenant_lease_ended_hint' : 'stay_qr_hint'),
                  style: const TextStyle(color: Colors.white70, fontSize: 13),
                ),
                if (unit.lease!.meterReadings.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  MeterReadingsCard(readings: unit.lease!.meterReadings, showExit: unit.lease!.isEnded),
                ],
              ],
            ),
          ),
      ],
    );
  }
}
