import 'package:flutter/material.dart';
import '../api.dart';
import '../theme.dart';
import '../widgets.dart';

class StockScreen extends StatefulWidget {
  final ApiService api;
  const StockScreen({super.key, required this.api});
  @override
  State<StockScreen> createState() => _StockScreenState();
}

class _StockScreenState extends State<StockScreen> {
  final controller = TextEditingController();
  Map<String, dynamic>? data;
  ApiException? error;
  bool loading = false;

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final t = controller.text.trim().toUpperCase();
    if (t.isEmpty) return;
    FocusScope.of(context).unfocus();
    setState(() {
      loading = true;
      error = null;
      data = null;
    });
    try {
      final d = await widget.api.stock(t);
      if (mounted) setState(() => data = d);
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                textInputAction: TextInputAction.search,
                onSubmitted: (_) => _search(),
                decoration: const InputDecoration(hintText: 'Enter a PSX symbol, e.g. MCB'),
              ),
            ),
            const SizedBox(width: 10),
            FilledButton(onPressed: loading ? null : _search, child: const Text('Search')),
          ],
        ),
        const SizedBox(height: 16),
        if (loading) const LoadingView(),
        if (error != null) ErrorView(error: error!, baseUrl: widget.api.baseUrl),
        if (data != null) ..._detail(data!),
      ],
    );
  }

  List<Widget> _detail(Map<String, dynamic> d) {
    final price = (d['price'] ?? {}) as Map;
    final sc = (d['scoring'] ?? {}) as Map;
    final sent = d['news_sentiment'] as Map?;
    final chg = (price['change_pct'] is num) ? price['change_pct'] as num : num.tryParse('${price['change_pct']}') ?? 0;

    return [
      SectionCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${d['symbol']} · ${d['sector'] ?? ''}',
                style: const TextStyle(color: AppColors.muted, fontSize: 12)),
            Text('${d['company'] ?? ''}', style: const TextStyle(fontSize: 15)),
            const SizedBox(height: 14),
            Wrap(spacing: 22, runSpacing: 10, children: [
              _kv('Close', fmtNum(price['close'])),
              _kv('Change %', fmtNum(chg), color: chg >= 0 ? AppColors.green : AppColors.red),
              _kv('Volume', fmtNum(price['volume'], digits: 0)),
              _kv('Date', '${price['date'] ?? '—'}'),
            ]),
          ],
        ),
      ),
      const SizedBox(height: 12),
      SectionCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              PillBadge('${sc['final_decision']}', decisionColor('${sc['final_decision']}')),
              const SizedBox(width: 10),
              Text('risk: ${sc['risk_permission'] ?? '—'}', style: const TextStyle(color: AppColors.muted)),
            ]),
            const SizedBox(height: 14),
            Wrap(spacing: 22, runSpacing: 10, children: [
              _kv('Buy probability', fmtNum(sc['buy_probability'], digits: 1)),
              _kv('Smart money', fmtNum(sc['smart_money_score'], digits: 0)),
              _kv('Stop loss', fmtNum(sc['stop_loss'])),
              _kv('Target 1', fmtNum(sc['target_1'])),
              _kv('Target 2', fmtNum(sc['target_2'])),
              _kv('Entry timing', '${sc['entry_timing_action'] ?? '—'}'),
            ]),
          ],
        ),
      ),
      const SizedBox(height: 12),
      SectionCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('NEWS SENTIMENT',
                style: TextStyle(color: AppColors.muted, fontSize: 12, letterSpacing: 0.5, fontWeight: FontWeight.w700)),
            const SizedBox(height: 10),
            if (sent == null)
              const Text('No news matched this ticker in today’s feeds.', style: TextStyle(color: AppColors.muted))
            else ...[
              Row(children: [
                PillBadge('${sent['sentiment_label']}',
                    sent['sentiment_label'] == 'BULLISH'
                        ? AppColors.green
                        : sent['sentiment_label'] == 'BEARISH'
                            ? AppColors.red
                            : AppColors.amber),
                const SizedBox(width: 10),
                Text('score ${fmtNum(sent['sentiment_score'])} · ${sent['n_headlines']} headline(s)',
                    style: const TextStyle(color: AppColors.muted)),
              ]),
              const SizedBox(height: 8),
              for (final h in List<dynamic>.from(sent['sample_headlines'] ?? []))
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Text('“${h['title']}” — ${h['source']} (${h['label']})',
                      style: const TextStyle(fontSize: 13)),
                ),
            ],
          ],
        ),
      ),
    ];
  }

  Widget _kv(String k, String v, {Color? color}) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(k, style: const TextStyle(color: AppColors.muted, fontSize: 11)),
          Text(v, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18, color: color ?? AppColors.text)),
        ],
      );
}
