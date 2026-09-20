import 'dart:math';

import 'package:flutter/material.dart';

/// Branded replacement for [CircularProgressIndicator] — a rotating ring in
/// the liquid-glass-blue gradient, echoing the OWC hub-ring mark instead of
/// Material's default spinner.
class AppLoadingIndicator extends StatefulWidget {
  const AppLoadingIndicator({Key? key, this.size = 28, this.strokeWidth = 3})
      : super(key: key);

  final double size;
  final double strokeWidth;

  @override
  State<AppLoadingIndicator> createState() => _AppLoadingIndicatorState();
}

class _AppLoadingIndicatorState extends State<AppLoadingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) => CustomPaint(
          painter: _RingPainter(
            progress: _controller.value,
            strokeWidth: widget.strokeWidth,
          ),
        ),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  _RingPainter({required this.progress, required this.strokeWidth});

  final double progress;
  final double strokeWidth;

  static const _track = Color(0x332E8BFF);
  static const _gradient = SweepGradient(
    colors: [Color(0xFF2EE7FF), Color(0xFF2E8BFF), Color(0xFF1A5FE0), Color(0xFF2EE7FF)],
  );

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = (size.shortestSide - strokeWidth) / 2;
    final rect = Rect.fromCircle(center: center, radius: radius);

    final trackPaint = Paint()
      ..color = _track
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;
    canvas.drawCircle(center, radius, trackPaint);

    // Sweep length breathes between ~18% and ~78% of the ring while it spins,
    // the same "draws itself, holds, resets" rhythm as the splash mark.
    final breathe = (sin(progress * 2 * pi) + 1) / 2;
    final sweep = (0.18 + breathe * 0.6) * 2 * pi;
    final startAngle = -pi / 2 + progress * 2 * pi;

    final arcPaint = Paint()
      ..shader = _gradient.createShader(rect)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;

    canvas.drawArc(rect, startAngle, sweep, false, arcPaint);
  }

  @override
  bool shouldRepaint(covariant _RingPainter oldDelegate) =>
      oldDelegate.progress != progress || oldDelegate.strokeWidth != strokeWidth;
}
