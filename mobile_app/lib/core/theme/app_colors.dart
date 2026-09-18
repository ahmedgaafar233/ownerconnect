import 'package:flutter/material.dart';

class AppColors {
  static const Color primary = Color(0xFF1E3A8A);      // Deep Navy Blue
  static const Color primaryLight = Color(0xFF3B82F6); // Vibrant Blue
  static const Color secondary = Color(0xFF0D9488);    // Rich Teal
  static const Color accent = Color(0xFFF59E0B);       // Warm Amber

  static const Color background = Color(0xFFF8FAFC);   // Soft Light Slate
  static const Color surface = Color(0xFFFFFFFF);      // Pure White
  static const Color cardBg = Color(0xFFFFFFFF);

  static const Color textPrimary = Color(0xFF0F172A);  // Dark Slate Text
  static const Color textSecondary = Color(0xFF64748B);// Muted Slate Text
  static const Color border = Color(0xFFE2E8F0);

  static const Color success = Color(0xFF10B981);      // Emerald Green
  static const Color warning = Color(0xFFF59E0B);      // Amber Alert
  static const Color error = Color(0xFFEF4444);        // Crimson Red

  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF1E3A8A), Color(0xFF2563EB)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}
