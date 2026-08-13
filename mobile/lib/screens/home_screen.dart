import 'package:flutter/material.dart';
import '../api.dart';
import '../theme.dart';
import 'webview_screen.dart';

class _Feature {
  final String label;
  final String desc;
  final IconData icon;
  final Color color;
  final String section; // matches an id in the web page (webui.html)
  const _Feature(this.label, this.desc, this.icon, this.color, this.section);
}

/// Home = a launcher grid of every feature. Tapping one opens the built-in web
/// dashboard focused on that section (rich rendering, always in sync with the API).
class HomeScreen extends StatelessWidget {
  final ApiService api;
  const HomeScreen({super.key, required this.api});

  static const _features = <_Feature>[
    _Feature('AI Assistant', 'Ask about the data', Icons.chat_bubble_rounded, AppColors.blue, 'askCard'),
    _Feature('Morning Briefing', 'Pre-market summary', Icons.wb_sunny_rounded, AppColors.amber, 'briefCard'),
    _Feature("Today's Highlights", 'All triggers, one place', Icons.local_fire_department_rounded, AppColors.red, 'hlCard'),
    _Feature('Model Ranking', 'Contrarian research', Icons.psychology_alt_rounded, AppColors.blue, 'modelCard'),
    _Feature('Watchlist', 'Your tracked stocks', Icons.star_rounded, AppColors.amber, 'wlCard'),
    _Feature('Daily Signal', 'Market verdict', Icons.speed_rounded, AppColors.green, 'signalCard'),
    _Feature('Screeners', 'Breakouts, value, more', Icons.filter_alt_rounded, AppColors.blue, 'screenersCard'),
    _Feature('Sector Rotation', 'Where money flows', Icons.pie_chart_rounded, AppColors.green, 'sectorsCard'),
    _Feature('All Stocks', 'Ranked, paginated', Icons.format_list_numbered_rounded, AppColors.text, 'allStocksCard'),
    _Feature('Seasonality', 'Day / month patterns', Icons.calendar_month_rounded, AppColors.amber, 'seasonalityCard'),
    _Feature('Opportunities', 'Top-ranked names', Icons.trending_up_rounded, AppColors.green, 'oppsCard'),
    _Feature('Position Calculator', 'Size & risk', Icons.calculate_rounded, AppColors.blue, 'calcCard'),
    _Feature('Stock Lookup', 'Full per-stock panel', Icons.search_rounded, AppColors.text, 'lookupCard'),
  ];

  void _open(BuildContext ctx, _Feature f) {
    final base = api.baseUrl.replaceAll(RegExp(r'/+$'), '');
    final url = '$base/#key=${Uri.encodeComponent(api.apiKey)}&sec=${f.section}';
    Navigator.of(ctx).push(MaterialPageRoute(
      builder: (_) => WebViewScreen(url: url, title: f.label),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(14, 16, 14, 20),
      children: [
        const Text('PSX AI Scanner',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
        const SizedBox(height: 2),
        const Text('Tap any tool to open it',
            style: TextStyle(color: AppColors.muted, fontSize: 13)),
        const SizedBox(height: 16),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 1.25,
          children: _features.map((f) => _tile(context, f)).toList(),
        ),
      ],
    );
  }

  Widget _tile(BuildContext ctx, _Feature f) => InkWell(
        onTap: () => _open(ctx, f),
        borderRadius: BorderRadius.circular(16),
        child: Container(
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.borderSoft),
          ),
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(9),
                decoration: BoxDecoration(
                  color: f.color.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: Icon(f.icon, color: f.color, size: 24),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(f.label,
                      style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14.5)),
                  const SizedBox(height: 2),
                  Text(f.desc,
                      style: const TextStyle(color: AppColors.muted, fontSize: 11.5)),
                ],
              ),
            ],
          ),
        ),
      );
}
