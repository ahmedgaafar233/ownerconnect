import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/utils/app_localizations.dart';
import '../../data/models/lease_model.dart';
import '../../data/models/profile_unit.dart';
import 'lease_status_badge.dart';
import 'unit_labels.dart';

/// One of the person's units: what it is, its access cards, and — for an
/// owner — whether it's rented out (or a button to rent it out).
class ProfileUnitCard extends StatelessWidget {
  const ProfileUnitCard({
    Key? key,
    required this.unit,
    required this.onRentOut,
    required this.onOpenLease,
  }) : super(key: key);

  final ProfileUnit unit;
  final VoidCallback onRentOut;
  final VoidCallback onOpenLease;

  String? get _where {
    final parts = [
      unit.unitTypeName,
      if (unit.buildingNo.isNotEmpty) unit.buildingNo,
      if (unit.unitNo.isNotEmpty) unit.unitNo,
    ].whereType<String>().where((part) => part.isNotEmpty).toList();
    return parts.isEmpty ? null : parts.join(' · ');
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final where = _where;
    final lease = unit.lease;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.home_work_outlined, color: AppColors.primary),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(unit.unitKey, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                    if (where != null)
                      Text(where, style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
                  ],
                ),
              ),
              if (!unit.isOwnerUnit)
                Text(loc.translate('role_tenant'), style: const TextStyle(color: AppColors.textSecondary)),
            ],
          ),
          if (unit.cardAllowance != null) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                const Icon(Icons.credit_card, size: 18, color: AppColors.textSecondary),
                const SizedBox(width: 8),
                Text(
                  '${loc.translate('profile_unit_cards')}: ${unit.cardsUsed} / ${unit.cardAllowance}',
                  style: const TextStyle(color: AppColors.textSecondary),
                ),
              ],
            ),
          ],
          const SizedBox(height: 12),
          if (unit.isOwnerUnit) ...[
            // A rental still running (or coming up) takes the place of the
            // button; one that has ended stays visible — its tenant may still
            // owe — but the unit can be rented out again right away.
            if (lease != null) _LeaseBanner(lease: lease, onTap: onOpenLease),
            if (lease == null || lease.isEnded) ...[
              if (lease != null) const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: onRentOut,
                icon: const Icon(Icons.key_outlined, size: 18),
                label: Text(loc.translate('rent_out_button')),
              ),
            ],
          ]
          else if (lease != null) ...[
            Text(
              fillIn(loc.translate('tenant_lease_line'), [
                formatServerDate(context, lease.startDate),
                formatServerDate(context, lease.endDate),
              ]),
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            if (lease.isEnded) ...[
              const SizedBox(height: 6),
              Text(
                loc.translate('tenant_lease_ended_hint'),
                style: const TextStyle(color: AppColors.warning, fontWeight: FontWeight.w600),
              ),
            ],
          ],
        ],
      ),
    );
  }
}

/// The unit's rental in one tappable line: who, when, and its state.
class _LeaseBanner extends StatelessWidget {
  const _LeaseBanner({required this.lease, required this.onTap});

  final LeaseModel lease;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.glassFill,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    fillIn(loc.translate('rent_rented_to'), [lease.tenantName]),
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${formatServerDate(context, lease.startDate)} – ${formatServerDate(context, lease.endDate)}',
                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
                  ),
                ],
              ),
            ),
            LeaseStatusBadge(status: lease.status),
            const Icon(Icons.chevron_right, color: AppColors.textSecondary),
          ],
        ),
      ),
    );
  }
}
