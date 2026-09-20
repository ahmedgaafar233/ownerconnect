import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// Wraps [child] with a diagonal light sweep that loops continuously —
/// the shimmer used to skeleton-load cards/rows while real data is fetched.
class ShimmerLoading extends StatefulWidget {
  const ShimmerLoading({Key? key, required this.child}) : super(key: key);

  final Widget child;

  @override
  State<ShimmerLoading> createState() => _ShimmerLoadingState();
}

class _ShimmerLoadingState extends State<ShimmerLoading>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1500),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return ShaderMask(
          blendMode: BlendMode.srcATop,
          shaderCallback: (bounds) {
            final dx = bounds.width * (_controller.value * 2.6 - 0.8);
            return LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: const [
                Color(0x14241F18),
                Color(0x59241F18),
                Color(0x14241F18),
              ],
              stops: const [0.35, 0.5, 0.65],
              transform: _SlideGradientTransform(dx),
            ).createShader(bounds);
          },
          child: child,
        );
      },
      child: widget.child,
    );
  }
}

class _SlideGradientTransform extends GradientTransform {
  const _SlideGradientTransform(this.dx);

  final double dx;

  @override
  Matrix4? transform(Rect bounds, {TextDirection? textDirection}) =>
      Matrix4.translationValues(dx, 0, 0);
}

/// A single skeleton block — a rounded, faintly-glassy rectangle wrapped in
/// [ShimmerLoading]. Compose several to build a skeleton for a card or row.
class ShimmerBox extends StatelessWidget {
  const ShimmerBox({
    Key? key,
    required this.width,
    required this.height,
    this.borderRadius = 12,
  }) : super(key: key);

  final double width;
  final double height;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    return ShimmerLoading(
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: AppColors.glassFill,
          borderRadius: BorderRadius.circular(borderRadius),
        ),
      ),
    );
  }
}
