import 'package:flutter/material.dart';
import 'theme.dart';
import 'api.dart';

String fmtNum(dynamic v, {int digits = 2}) {
  if (v == null) return '—';
  final n = v is num ? v : num.tryParse(v.toString());
  if (n == null) return '—';
  return n.toStringAsFixed(digits);
}

class LoadingView extends StatelessWidget {
  const LoadingView({super.key});
  @override
  Widget build(BuildContext context) =>
      const Center(child: Padding(padding: EdgeInsets.all(40), child: CircularProgressIndicator()));
}

/// Error state. Uses a distinct "not connected" treatment for connection errors,
/// since the backend runs on the user's PC and the phone must share its network.
class ErrorView extends StatelessWidget {
  final ApiException error;
  final VoidCallback? onRetry;
  final String? baseUrl;
  const ErrorView({super.key, required this.error, this.onRetry, this.baseUrl});

  @override
  Widget build(BuildContext context) {
    final connection = error.isConnection;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(connection ? Icons.wifi_off_rounded : Icons.error_outline_rounded,
                size: 48, color: AppColors.red),
            const SizedBox(height: 14),
            Text(connection ? 'Not connected' : 'Something went wrong',
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            Text(error.message,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.muted)),
            if (connection && baseUrl != null) ...[
              const SizedBox(height: 6),
              Text('Base URL: $baseUrl',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppColors.muted, fontSize: 12)),
              const SizedBox(height: 6),
              const Text('Make sure the backend is running and the phone is on the same WiFi.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.muted, fontSize: 12)),
            ],
            if (onRetry != null) ...[
              const SizedBox(height: 16),
              FilledButton(onPressed: onRetry, child: const Text('Retry')),
            ],
          ],
        ),
      ),
    );
  }
}

class SectionCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  const SectionCard({super.key, required this.child, this.padding = const EdgeInsets.all(16)});
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: padding,
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.border),
        ),
        child: child,
      );
}

class PillBadge extends StatelessWidget {
  final String text;
  final Color color;
  const PillBadge(this.text, this.color, {super.key});
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.16),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(text,
            style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 12)),
      );
}

class Chip2 extends StatelessWidget {
  final Widget child;
  const Chip2({super.key, required this.child});
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: const Color(0xFF10243A),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: AppColors.borderSoft),
        ),
        child: child,
      );
}
