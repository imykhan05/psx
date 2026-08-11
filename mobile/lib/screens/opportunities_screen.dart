import 'package:flutter/material.dart';
import '../api.dart';
import '../theme.dart';
import '../widgets.dart';

class OpportunitiesScreen extends StatefulWidget {
  final ApiService api;
  const OpportunitiesScreen({super.key, required this.api});
  @override
  State<OpportunitiesScreen> createState() => _OpportunitiesScreenState();
}

class _OpportunitiesScreenState extends State<OpportunitiesScreen> {
  List<dynamic> rows = [];
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
      final r = await widget.api.opportunities(limit: 100);
      if (mounted) setState(() => rows = r);
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
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.all(16),
        itemCount: rows.isEmpty ? 1 : rows.length,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (context, i) {
          if (rows.isEmpty) {
            return const Padding(
              padding: EdgeInsets.only(top: 40),
              child: Center(child: Text('No opportunities in the latest scan.', style: TextStyle(color: AppColors.muted))),
            );
          }
          final r = rows[i] as Map;
          final chg = (r['change_pct'] is num) ? r['change_pct'] as num : num.tryParse('${r['change_pct']}') ?? 0;
          return SectionCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${r['symbol']}', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                          Text('${r['company'] ?? ''} · ${r['sector'] ?? ''}',
                              style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                        ],
                      ),
                    ),
                    PillBadge('${r['final_decision']}', decisionColor('${r['final_decision']}')),
                  ],
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 16,
                  runSpacing: 8,
                  children: [
                    _kv('Close', fmtNum(r['close'])),
                    _kv('Chg %', fmtNum(chg), color: chg >= 0 ? AppColors.green : AppColors.red),
                    _kv('Buy prob', fmtNum(r['buy_probability'], digits: 1)),
                    _kv('Stop', fmtNum(r['stop_loss'])),
                    _kv('Target 1', fmtNum(r['target_1'])),
                    _kv('Target 2', fmtNum(r['target_2'])),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _kv(String k, String v, {Color? color}) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(k, style: const TextStyle(color: AppColors.muted, fontSize: 11)),
          Text(v, style: TextStyle(fontWeight: FontWeight.w700, color: color ?? AppColors.text)),
        ],
      );
}
