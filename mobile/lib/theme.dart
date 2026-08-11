import 'package:flutter/material.dart';

/// Dark trading-terminal palette, matching the React dashboard.
class AppColors {
  static const bg = Color(0xFF07111F);
  static const bgElev = Color(0xFF0B1727);
  static const card = Color(0xFF0D1C2D);
  static const border = Color(0xFF21415F);
  static const borderSoft = Color(0xFF1B3852);
  static const text = Color(0xFFEDF4FB);
  static const muted = Color(0xFF91A8BD);
  static const green = Color(0xFF32D296);
  static const red = Color(0xFFFF6474);
  static const amber = Color(0xFFF5C451);
  static const blue = Color(0xFF58A6FF);
}

Color verdictColor(String? verdict) {
  switch ((verdict ?? '').toUpperCase()) {
    case 'BULLISH':
      return AppColors.green;
    case 'BEARISH':
      return AppColors.red;
    case 'NEUTRAL':
      return AppColors.amber;
    default:
      return AppColors.muted;
  }
}

/// Colour for a decision badge (BUY/WATCH/AVOID family).
Color decisionColor(String? decision) {
  final d = (decision ?? '').toUpperCase();
  if (d.contains('STRONG BUY') || d == 'BUY' || d == 'ACCUMULATE') {
    return AppColors.green;
  }
  if (d.contains('WATCH') || d.contains('WAIT')) return AppColors.amber;
  return AppColors.red;
}

ThemeData buildTheme() {
  final base = ThemeData.dark(useMaterial3: true);
  return base.copyWith(
    scaffoldBackgroundColor: AppColors.bg,
    colorScheme: base.colorScheme.copyWith(
      primary: AppColors.blue,
      surface: AppColors.card,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.bgElev,
      foregroundColor: AppColors.text,
      elevation: 0,
    ),
    cardColor: AppColors.card,
    dividerColor: AppColors.borderSoft,
    textTheme: base.textTheme.apply(
      bodyColor: AppColors.text,
      displayColor: AppColors.text,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.card,
      hintStyle: const TextStyle(color: AppColors.muted),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.blue),
      ),
    ),
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: AppColors.bgElev,
      selectedItemColor: AppColors.blue,
      unselectedItemColor: AppColors.muted,
      type: BottomNavigationBarType.fixed,
    ),
  );
}
