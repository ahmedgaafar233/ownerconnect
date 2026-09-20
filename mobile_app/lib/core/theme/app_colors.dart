import 'package:flutter/material.dart';

/// Liquid-glass blue on cream — confirmed 2026-09-20: the dark indigo ground
/// was dropped for a warm cream ground, buttons/accents kept exactly as they
/// were (vivid blue primary, sky-blue secondary, cyan CTA glass tint).
class AppColors {
  static const Color primary = Color(0xFF2E8BFF); // Vivid Blue
  static const Color primaryDeep = Color(0xFF1A5FE0); // Deep Blue (gradient stop)
  static const Color primaryLight = Color(0xFF45C6FF); // Sky Blue
  static const Color secondary = Color(0xFF45C6FF); // Sky Blue
  static const Color cta = Color(0xFF2EE7FF); // Bright Cyan — primary CTA glass tint
  static const Color accent = Color(0xFFF59E0B); // Amber — functional warning only, not decorative
  static const Color onAccent = Color(0xFF0B1030); // fixed dark ink for text/icons on top of primary/cta — independent of page brightness

  static const Color background = Color(0xFFF7F2E7); // Warm Cream
  static const Color backgroundElevated = Color(0xFFEFE7D3); // Deeper Cream (drawer/dialogs)
  static const Color surface = Color(0xFFFFFDF7); // Near-white card surface
  static const Color cardBg = Color(0xFFFFFDF7);
  static const Color glassFill = Color(0x142E8BFF); // faint blue-tinted glass fill on cream

  static const Color textPrimary = Color(0xFF241F18); // Warm near-black
  static const Color textSecondary = Color(0xFF6B675E); // Warm muted gray
  static const Color textTertiary = Color(0xFF9C9587);
  static const Color border = Color(0xFFE3DCC9); // warm hairline border for light surfaces

  static const Color success = Color(0xFF10B981); // Emerald Green
  static const Color warning = Color(0xFFF59E0B); // Amber Alert
  static const Color error = Color(0xFFEF4444); // Crimson Red

  static const LinearGradient primaryGradient = LinearGradient(
    colors: [primaryDeep, primary],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient ctaGradient = LinearGradient(
    colors: [primary, cta],
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
  );
}
