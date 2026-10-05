import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_connect/core/widgets/wave_bottom_nav.dart';

const _items = [
  WaveNavItem(icon: Icons.account_balance_wallet_rounded, label: 'Charges'),
  WaveNavItem(icon: Icons.support_agent_rounded, label: 'Support'),
  WaveNavItem(icon: Icons.qr_code_2_rounded, label: 'Passes'),
];

class _Host extends StatefulWidget {
  const _Host({this.rtl = false, this.onChanged});

  final bool rtl;
  final ValueChanged<int>? onChanged;

  @override
  State<_Host> createState() => _HostState();
}

class _HostState extends State<_Host> {
  int index = 0;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Directionality(
        textDirection: widget.rtl ? TextDirection.rtl : TextDirection.ltr,
        child: Scaffold(
          bottomNavigationBar: WaveBottomNav(
            items: _items,
            currentIndex: index,
            onTap: (i) {
              widget.onChanged?.call(i);
              setState(() => index = i);
            },
          ),
        ),
      ),
    );
  }
}

/// The raised bubble holds the selected tab's icon: white, 26 px.
Finder get _bubbleIcon => find.byWidgetPredicate((w) => w is Icon && w.size == 26 && w.color == Colors.white);

void main() {
  testWidgets('tapping a tab reports it, and the bubble glides over to it', (tester) async {
    final taps = <int>[];
    await tester.pumpWidget(_Host(onChanged: taps.add));
    await tester.pumpAndSettle();
    final before = tester.getCenter(_bubbleIcon).dx;

    await tester.tap(find.text('Passes'));
    await tester.pumpAndSettle();

    expect(taps, [2]);
    expect(tester.getCenter(_bubbleIcon).dx, greaterThan(before));
    expect(find.descendant(of: find.byType(WaveBottomNav), matching: find.byIcon(Icons.qr_code_2_rounded)), findsWidgets);
  });

  testWidgets('the bubble sits above the bar and bounces back to rest after a tap', (tester) async {
    await tester.pumpWidget(const _Host());
    await tester.pumpAndSettle();
    final rest = tester.getCenter(_bubbleIcon).dy;

    await tester.tap(find.text('Support'));
    await tester.pump(const Duration(milliseconds: 120));
    final rising = tester.getCenter(_bubbleIcon).dy;
    await tester.pumpAndSettle();

    expect(rising, isNot(equals(rest))); // it moves while popping…
    expect(tester.getCenter(_bubbleIcon).dy, closeTo(rest, 0.5)); // …and settles at the same height
  });

  testWidgets('every label is shown and each tab is a labelled button for screen readers', (tester) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(const _Host());
    await tester.pumpAndSettle();

    for (final label in ['Charges', 'Support', 'Passes']) {
      expect(find.text(label), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp(label)), findsWidgets);
    }
    semantics.dispose();
  });

  testWidgets('in a right-to-left language the first tab is on the right and the bubble follows it', (tester) async {
    await tester.pumpWidget(const _Host(rtl: true));
    await tester.pumpAndSettle();

    expect(tester.getCenter(find.text('Charges')).dx, greaterThan(tester.getCenter(find.text('Passes')).dx));
    final charges = tester.getCenter(_bubbleIcon).dx;

    await tester.tap(find.text('Passes'));
    await tester.pumpAndSettle();
    expect(tester.getCenter(_bubbleIcon).dx, lessThan(charges));
  });

  testWidgets('tapping quickly through tabs never throws and ends on the last one', (tester) async {
    final taps = <int>[];
    await tester.pumpWidget(_Host(onChanged: taps.add));
    await tester.tap(find.text('Support'));
    await tester.pump(const Duration(milliseconds: 80));
    await tester.tap(find.text('Passes'));
    await tester.pump(const Duration(milliseconds: 80));
    await tester.tap(find.text('Charges'));
    await tester.pumpAndSettle();

    expect(taps, [1, 2, 0]);
    expect(tester.takeException(), isNull);
  });
}
