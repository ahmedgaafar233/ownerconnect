import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/utils/app_localizations.dart';
import '../../../auth/presentation/bloc/auth_bloc.dart';
import '../../../auth/presentation/bloc/auth_event.dart';
import '../../../auth/presentation/bloc/auth_state.dart';
import '../../../financial/presentation/screens/charges_screen.dart';
import '../../../support/presentation/screens/support_tickets_screen.dart';
import '../../../support/presentation/screens/visitor_passes_screen.dart';

/// Authenticated app shell. Only ever reached via the router when AuthBloc
/// is in AuthenticatedState — its AppBar showing the resort name is the
/// visible proof the app is locked to the signed-in owner's own village.
class HomeShell extends StatefulWidget {
  const HomeShell({Key? key}) : super(key: key);

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    ChargesScreen(),
    SupportTicketsScreen(),
    VisitorPassesScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final authState = context.watch<AuthBloc>().state;
    final resortName = authState is AuthenticatedState ? authState.resortName : '';

    return Scaffold(
      appBar: AppBar(
        title: Text(resortName.isNotEmpty ? resortName : loc.translate('app_title')),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: loc.translate('logout'),
            onPressed: () => context.read<AuthBloc>().add(const LogoutRequested()),
          ),
        ],
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) => setState(() => _currentIndex = index),
        items: [
          BottomNavigationBarItem(
            icon: const Icon(Icons.account_balance_wallet),
            label: loc.translate('charges_title'),
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.support_agent),
            label: loc.translate('tickets_title'),
          ),
          BottomNavigationBarItem(
            icon: const Icon(Icons.qr_code_2),
            label: loc.translate('passes_title'),
          ),
        ],
      ),
    );
  }
}
