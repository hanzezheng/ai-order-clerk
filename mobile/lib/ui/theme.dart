import 'package:flutter/material.dart';

final stallTheme = ThemeData(
  useMaterial3: true,
  colorScheme: ColorScheme.light(
    primary: const Color(0xFF1F7A4D),
    onPrimary: Colors.white,
    surface: const Color(0xFFF6F1E4),
    onSurface: const Color(0xFF1B241C),
    secondary: const Color(0xFFC9A227),
  ),
  scaffoldBackgroundColor: const Color(0xFFF6F1E4),
  textTheme: const TextTheme(
    headlineLarge: TextStyle(fontSize: 32, fontWeight: FontWeight.w700, height: 1.2),
    headlineMedium: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, height: 1.25),
    titleLarge: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
    bodyLarge: TextStyle(fontSize: 20, height: 1.35),
    bodyMedium: TextStyle(fontSize: 16, height: 1.35),
  ),
);
