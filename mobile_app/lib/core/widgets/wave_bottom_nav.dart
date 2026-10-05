import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

class WaveNavItem {
  final IconData icon;
  final String label;

  const WaveNavItem({required this.icon, required this.label});
}

/// Bottom bar whose selected tab pops out of the bar: the bar scoops a
/// round notch around it, the notch glides to the newly chosen tab, and the
/// tab's icon rides up in a glowing bubble with a springy bounce.
class WaveBottomNav extends StatefulWidget {
  const WaveBottomNav({
    Key? key,
    required this.items,
    required this.currentIndex,
    required this.onTap,
  }) : super(key: key);

  final List<WaveNavItem> items;
  final int currentIndex;
  final ValueChanged<int> onTap;

  @override
  State<WaveBottomNav> createState() => _WaveBottomNavState();
}

class _WaveBottomNavState extends State<WaveBottomNav> with TickerProviderStateMixin {
  static const double _barHeight = 74;
  static const double _popRoom = 30; // room above the bar for the raised bubble
  static const double _bubble = 56;

  late final AnimationController _slide =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 460));
  late final AnimationController _pop =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 900));
  late double _from = widget.currentIndex.toDouble();
  late double _to = widget.currentIndex.toDouble();

  @override
  void initState() {
    super.initState();
    _slide.value = 1;
    _pop.value = 1;
  }

  @override
  void didUpdateWidget(WaveBottomNav old) {
    super.didUpdateWidget(old);
    if (old.currentIndex != widget.currentIndex) {
      // Start from wherever the notch is right now, so a quick second tap
      // redirects it smoothly instead of jumping.
      _from = _position;
      _to = widget.currentIndex.toDouble();
      _slide.forward(from: 0);
      _pop.forward(from: 0);
    }
  }

  @override
  void dispose() {
    _slide.dispose();
    _pop.dispose();
    super.dispose();
  }

  double get _position =>
      _from + (_to - _from) * Curves.easeInOutCubic.transform(_slide.value);

  @override
  Widget build(BuildContext context) {
    final rtl = Directionality.of(context) == TextDirection.rtl;
    final count = widget.items.length;

    return SafeArea(
      top: false,
      child: SizedBox(
        height: _popRoom + _barHeight,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final width = constraints.maxWidth;
            final slot = width / count;
            // Centre of tab [i] (a fraction for the gliding notch), mirrored for RTL.
            double centreOf(double i) => rtl ? width - (i + 0.5) * slot : (i + 0.5) * slot;

            return AnimatedBuilder(
              animation: Listenable.merge([_slide, _pop]),
              builder: (context, _) {
                final notchX = centreOf(_position);
                // 0 → bubble resting in the notch, 1 → fully raised (with overshoot from the spring).
                final lift = Curves.elasticOut.transform(_pop.value.clamp(0.0, 1.0));
                final bubbleTop = _popRoom - _bubble / 2 - 10 * lift;

                return Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Positioned.fill(
                      top: _popRoom,
                      child: CustomPaint(painter: _BarPainter(notchX: notchX, notchRadius: _bubble / 2 + 8)),
                    ),
                    Positioned(
                      left: notchX - _bubble / 2,
                      top: bubbleTop,
                      child: IgnorePointer(
                        child: Transform.scale(
                          scale: 0.8 + 0.2 * lift,
                          child: Container(
                            width: _bubble,
                            height: _bubble,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: const LinearGradient(
                                begin: Alignment.topLeft,
                                end: Alignment.bottomRight,
                                colors: [AppColors.primary, AppColors.primaryLight],
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: AppColors.primary.withOpacity(0.45),
                                  blurRadius: 18,
                                  offset: const Offset(0, 8),
                                ),
                              ],
                            ),
                            child: Icon(
                              widget.items[widget.currentIndex.clamp(0, count - 1)].icon,
                              color: Colors.white,
                              size: 26,
                            ),
                          ),
                        ),
                      ),
                    ),
                    Positioned.fill(
                      top: _popRoom,
                      child: Row(
                        children: [
                          for (var i = 0; i < count; i++)
                            Expanded(
                              child: _NavSlot(
                                item: widget.items[i],
                                selected: i == widget.currentIndex,
                                onTap: () => widget.onTap(i),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ],
                );
              },
            );
          },
        ),
      ),
    );
  }
}

class _NavSlot extends StatelessWidget {
  const _NavSlot({required this.item, required this.selected, required this.onTap});

  final WaveNavItem item;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: selected,
      label: item.label,
      child: InkResponse(
        onTap: onTap,
        radius: 44,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            // The selected icon lives in the raised bubble; keep its slot empty
            // so the label sits right under it.
            AnimatedOpacity(
              duration: const Duration(milliseconds: 200),
              opacity: selected ? 0 : 1,
              child: Icon(item.icon, size: 24, color: AppColors.textTertiary),
            ),
            const SizedBox(height: 4),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: AnimatedDefaultTextStyle(
                duration: const Duration(milliseconds: 250),
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: selected ? FontWeight.w800 : FontWeight.w500,
                  color: selected ? AppColors.primary : AppColors.textTertiary,
                ),
                child: Text(item.label, maxLines: 1, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center),
              ),
            ),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }
}

/// The bar itself: a rounded slab with a round bite taken out around the
/// raised tab, plus a soft shadow along the top edge.
class _BarPainter extends CustomPainter {
  _BarPainter({required this.notchX, required this.notchRadius});

  final double notchX;
  final double notchRadius;

  @override
  void paint(Canvas canvas, Size size) {
    final slab = Path()
      ..addRRect(RRect.fromRectAndCorners(
        Offset.zero & size,
        topLeft: const Radius.circular(26),
        topRight: const Radius.circular(26),
      ));
    final bite = Path()..addOval(Rect.fromCircle(center: Offset(notchX, 0), radius: notchRadius));
    final bar = Path.combine(PathOperation.difference, slab, bite);

    canvas.drawShadow(bar, Colors.black.withOpacity(0.25), 10, false);
    canvas.drawPath(bar, Paint()..color = AppColors.backgroundElevated);
  }

  @override
  bool shouldRepaint(_BarPainter old) => old.notchX != notchX || old.notchRadius != notchRadius;
}
