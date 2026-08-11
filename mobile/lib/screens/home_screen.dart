import 'package:flutter/material.dart';
import '../api.dart';
import '../theme.dart';
import '../widgets.dart';

class HomeScreen extends StatefulWidget {
  final ApiService api;
  const HomeScreen({super.key, required this.api});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Map<String, dynamic>? signal;
  ApiException? error;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final s = await widget.api.signal();
      if (mounted) setState(() => signal = s);
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const LoadingView();
    if (error != null) {
      return ErrorView(error: error!, onRetry: _load, baseUrl: widget.api.baseUrl);
    }
    final s = signal!;
    final color = verdictColor(s['verdict']?.toString());
    final confidence = (((s['confidence'] ?? 0) as num) * 100).round();
    final breadth = (s['breadth'] ?? {}) as Map;
    final sent = (s['sentiment_summary'] ?? {}) as Map;
    final reasons = List<dynamic>.from(s['reasons'] ?? []);
    final tops = List<dynamic>.from(s['top_opportunities'] ?? []);

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          SectionCard(
            padding: const EdgeInsets.all(22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s['verdict']?.toString() ?? '—',
                    style: TextStyle(fontSize: 54, fontWeight: FontWeight.w900, color: color, height: 1)),
                const SizedBox(height: 10),
                Text('Confidence $confidence%   ·   Trading date ${s['date'] ?? '—'}',
                    style: const TextStyle(color: AppColors.muted, fontSize: 15)),
                const SizedBox(height: 14),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  Chip2(
                    child: Text('Advancers ${breadth['advancers'] ?? '—'} / Decliners ${breadth['decliners'] ?? '—'}',
                        style: const TextStyle(color: AppColors.muted, fontSize: 13)),
                  ),
                  Chip2(
                    child: Text('News: ${sent['bullish'] ?? 0} bullish, ${sent['bearish'] ?? 0} bearish, ${sent['neutral'] ?? 0} neutral',
                        style: const TextStyle(color: AppColors.muted, fontSize: 13)),
                  ),
                ]),
                const SizedBox(height: 16),
                for (final r in reasons)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Text('•  $r', style: const TextStyle(fontSize: 15)),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('TOP OPPORTUNITIES',
                    style: TextStyle(color: AppColors.muted, fontSize: 12, letterSpacing: 0.5, fontWeight: FontWeight.w700)),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: tops.isEmpty
                      ? [const Text('None flagged today.', style: TextStyle(color: AppColors.muted))]
                      : [for (final t in tops) Chip2(child: Text(t.toString(), style: const TextStyle(fontWeight: FontWeight.w700)))],
                ),
                const SizedBox(height: 14),
                Text('Generated ${s['generated_at'] ?? ''} · decision-support from an end-of-day rule-based scan, not financial advice.',
                    style: const TextStyle(color: AppColors.muted, fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
