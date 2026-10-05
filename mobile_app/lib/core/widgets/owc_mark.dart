import 'package:flutter/material.dart';

/// The OWC brand mark: an interlocked O-ring / W-zigzag / C-arc crest in a
/// rounded-square badge — never typeset as plain "OWC" text. When [animate]
/// is true each stroke traces itself in sequence (O, then W, then C) like a
/// signature, then holds and loops.
///
/// Below ~80px the full O+W+C composition doesn't survive shrinking (same
/// problem as a launcher icon at 16px) — it automatically falls back to the
/// simplified ring-and-flourish mark used for the app icon instead of
/// rendering illegible detail.
class OwcMark extends StatefulWidget {
  const OwcMark({
    Key? key,
    this.size = 116,
    this.animate = true,
    this.duration = const Duration(milliseconds: 5000),
    this.loop = true,
  }) : super(key: key);

  final double size;
  final bool animate;

  /// One full cycle. The three letters finish drawing at 62% of it.
  final Duration duration;

  /// Repeat forever (the default, for a mark that just sits on screen), or
  /// draw once and hold the finished monogram — what a splash wants.
  final bool loop;

  @override
  State<OwcMark> createState() => _OwcMarkState();
}

class _OwcMarkState extends State<OwcMark> with SingleTickerProviderStateMixin {
  AnimationController? _controller;

  bool get _simple => widget.size < 80;

  @override
  void initState() {
    super.initState();
    if (widget.animate) {
      _controller = AnimationController(vsync: this, duration: widget.duration);
      widget.loop ? _controller!.repeat() : _controller!.forward();
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final radius = widget.size * (36 / 116);
    return Container(
      width: widget.size,
      height: widget.size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(radius),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            const Color(0xFF2E8BFF).withOpacity(0.20),
            const Color(0xFF0B1030).withOpacity(0.94),
          ],
        ),
        border: Border.all(color: const Color(0xFF2E8BFF).withOpacity(0.42)),
        boxShadow: [
          BoxShadow(color: const Color(0xFF2E8BFF).withOpacity(0.32), blurRadius: 40, spreadRadius: 2),
        ],
      ),
      child: _controller == null
          ? CustomPaint(painter: _OwcPainter(progress: 1, simple: _simple))
          : AnimatedBuilder(
              animation: _controller!,
              builder: (context, _) => CustomPaint(painter: _OwcPainter(progress: _controller!.value, simple: _simple)),
            ),
    );
  }
}

class _OwcPainter extends CustomPainter {
  _OwcPainter({required this.progress, required this.simple});

  final double progress;
  final bool simple;

  // Full monogram — same coordinate system as the design mockup's 116x116 viewBox.
  static final Path _oPath = Path()..addOval(Rect.fromCircle(center: const Offset(58, 48), radius: 20));
  static final Path _wPath = (Path()
        ..moveTo(24, 66)
        ..lineTo(34, 88)
        ..lineTo(44, 70)
        ..lineTo(54, 88)
        ..lineTo(64, 72));
  static final Path _cPath = (Path()
        ..moveTo(92, 55)
        ..arcToPoint(const Offset(92, 73), radius: const Radius.circular(15), largeArc: true));

  // Simple mark (small sizes / app icon) — a hub ring with one flourish arc.
  static final Path _simpleRing = Path()..addOval(Rect.fromCircle(center: const Offset(58, 45), radius: 21));
  static final Path _simpleFlourish = Path()
    ..moveTo(34, 61)
    ..quadraticBezierTo(58, 75, 87, 60);

  @override
  void paint(Canvas canvas, Size size) {
    final scale = size.width / 116;
    canvas.save();
    canvas.scale(scale, scale);

    if (simple) {
      _paintSimple(canvas);
    } else {
      _paintFull(canvas);
    }

    canvas.restore();
  }

  void _paintFull(Canvas canvas) {
    // Sequenced reveal windows within one loop: O draws 0-0.30, W 0.20-0.52, C 0.34-0.62, hold to 0.88.
    final oT = _segmentProgress(progress, 0.0, 0.30);
    final wT = _segmentProgress(progress, 0.20, 0.52);
    final cT = _segmentProgress(progress, 0.34, 0.62);

    _drawPartial(canvas, _oPath, oT, const Color(0xFF2E8BFF), 3.6);
    _drawPartial(canvas, _wPath, wT, const Color(0xFFF5F6FF), 3.2);
    _drawPartial(canvas, _cPath, cT, const Color(0xFFF5F6FF), 3.2);

    _drawNode(canvas, const Offset(42, 67), 2.6, const Color(0xFF2EE7FF), progress, 0.5);
    _drawNode(canvas, const Offset(79, 50), 2.6, const Color(0xFF45C6FF), progress, 0.58);
  }

  void _paintSimple(Canvas canvas) {
    // Ring is always fully drawn — only the flourish underneath animates —
    // so the mark never reads as a broken/partial shape at a glance.
    _drawPartial(canvas, _simpleRing, 1, const Color(0xFF2E8BFF), 5.5);
    final fT = _segmentProgress(progress, 0.05, 0.55);
    _drawPartial(canvas, _simpleFlourish, fT, const Color(0xFFF5F6FF), 4.5);
    _drawNode(canvas, const Offset(34, 61), 3.2, const Color(0xFFF5F6FF), 1, 0);
    _drawNode(canvas, const Offset(87, 60), 4.4, const Color(0xFF2EE7FF), progress, 0.5);
  }

  double _segmentProgress(double p, double start, double end) {
    if (p <= start) return 0;
    if (p >= end) return 1;
    return (p - start) / (end - start);
  }

  void _drawPartial(Canvas canvas, Path path, double t, Color color, double strokeWidth) {
    if (t <= 0) return;
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    if (t >= 1) {
      canvas.drawPath(path, paint);
      return;
    }
    for (final metric in path.computeMetrics()) {
      final extract = metric.extractPath(0, metric.length * t);
      canvas.drawPath(extract, paint);
    }
  }

  void _drawNode(Canvas canvas, Offset center, double radius, Color color, double progress, double appearAt) {
    if (progress < appearAt) return;
    final pulse = 0.85 + 0.3 * ((progress - appearAt) * 6).clamp(0.0, 1.0) * (1 - ((progress - appearAt) * 6).clamp(0.0, 1.0));
    canvas.drawCircle(center, radius * (1 + pulse * 0.15), Paint()..color = color);
  }

  @override
  bool shouldRepaint(covariant _OwcPainter oldDelegate) =>
      oldDelegate.progress != progress || oldDelegate.simple != simple;
}
