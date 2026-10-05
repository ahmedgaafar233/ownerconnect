import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/utils/app_localizations.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../auth/presentation/bloc/auth_event.dart';
import '../../../auth/presentation/bloc/auth_state.dart';
import '../../../financial/presentation/screens/charges_screen.dart';
import '../../../notifications/presentation/bloc/notification_bloc.dart';
import '../../../notifications/presentation/bloc/notification_event.dart';
import '../../../support/presentation/screens/support_tickets_screen.dart';
import '../../../support/presentation/screens/visitor_passes_screen.dart';
import '../../../../core/widgets/wave_bottom_nav.dart';
import '../bloc/home_tab_bloc.dart';
import '../bloc/home_tab_event.dart';
import '../bloc/home_tab_state.dart';
import '../widgets/app_drawer.dart';

/// Authenticated app shell. Only ever reached via the router when AuthBloc
/// is in AuthenticatedState — its AppBar showing the resort name is the
/// visible proof the app is locked to the signed-in owner's own village.
class HomeShell extends StatefulWidget {
  const HomeShell({Key? key}) : super(key: key);

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  final List<Widget> _screens = const [
    ChargesScreen(),
    SupportTicketsScreen(),
    VisitorPassesScreen(),
  ];

  @override
  void initState() {
    super.initState();
    context.read<NotificationBloc>().add(const FetchUnreadCountEvent());
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final authState = context.watch<AuthBloc>().state;
    final resortName = authState is AuthenticatedState ? authState.resortName : '';
    final unreadCount = context.watch<NotificationBloc>().state.unreadCount;

    return Scaffold(
      drawer: const AppDrawer(),
      appBar: AppBar(
        // The village name reads as a brand: all capitals, heavy weight.
        title: Text(
          (resortName.isNotEmpty ? resortName : loc.translate('app_title')).toUpperCase(),
          style: const TextStyle(fontWeight: FontWeight.w800, letterSpacing: 1.4, fontSize: 19),
        ),
        actions: [
          IconButton(
            icon: Badge(
              label: Text('$unreadCount'),
              isLabelVisible: unreadCount > 0,
              child: const Icon(Icons.notifications_outlined),
            ),
            tooltip: loc.translate('notifications_title'),
            onPressed: () => context.push('/notifications'),
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: loc.translate('logout'),
            onPressed: () => context.read<AuthBloc>().add(const LogoutRequested()),
          ),
        ],
      ),
      body: BlocBuilder<HomeTabBloc, HomeTabState>(
        builder: (context, tab) => IndexedStack(index: tab.index, children: _screens),
      ),
      bottomNavigationBar: BlocBuilder<HomeTabBloc, HomeTabState>(
        builder: (context, tab) => WaveBottomNav(
          currentIndex: tab.index,
          onTap: (index) => context.read<HomeTabBloc>().add(HomeTabSelected(index)),
          items: [
            WaveNavItem(icon: Icons.account_balance_wallet_rounded, label: loc.translate('charges_title')),
            WaveNavItem(icon: Icons.support_agent_rounded, label: loc.translate('tickets_title')),
            WaveNavItem(icon: Icons.qr_code_2_rounded, label: loc.translate('passes_title')),
          ],
        ),
      ),
    );
  }
}
