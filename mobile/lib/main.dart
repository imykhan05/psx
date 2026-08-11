import 'package:flutter/material.dart';
import 'api.dart';
import 'settings_store.dart';
import 'theme.dart';
import 'screens/home_screen.dart';
import 'screens/opportunities_screen.dart';
import 'screens/stock_screen.dart';
import 'screens/chat_screen.dart';
import 'screens/settings_screen.dart';

void main() => runApp(const PsxApp());

class PsxApp extends StatefulWidget {
  const PsxApp({super.key});
  @override
  State<PsxApp> createState() => _PsxAppState();
}

class _PsxAppState extends State<PsxApp> {
  final store = SettingsStore();
  String baseUrl = '';
  String apiKey = '';
  bool loaded = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    baseUrl = await store.getBaseUrl();
    apiKey = await store.getApiKey();
    if (mounted) setState(() => loaded = true);
  }

  @override
  Widget build(BuildContext context) {
    Widget home;
    if (!loaded) {
      home = const Scaffold(body: Center(child: CircularProgressIndicator()));
    } else if (apiKey.isEmpty) {
      home = SettingsScreen(store: store, isLogin: true, onSaved: _load);
    } else {
      home = RootShell(
        api: ApiService(baseUrl: baseUrl, apiKey: apiKey),
        store: store,
        onSettingsChanged: _load,
      );
    }
    return MaterialApp(
      title: 'PSX AI Scanner',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: home,
    );
  }
}

class RootShell extends StatefulWidget {
  final ApiService api;
  final SettingsStore store;
  final VoidCallback onSettingsChanged;
  const RootShell({super.key, required this.api, required this.store, required this.onSettingsChanged});
  @override
  State<RootShell> createState() => _RootShellState();
}

class _RootShellState extends State<RootShell> {
  int index = 0;
  static const titles = ['Daily Market Signal', 'Top Opportunities', 'Stock Lookup', 'AI Assistant'];

  @override
  Widget build(BuildContext context) {
    // Rebuild children when the api instance changes (e.g. after settings save).
    final pages = [
      HomeScreen(api: widget.api, key: ValueKey('home_${widget.api.baseUrl}')),
      OpportunitiesScreen(api: widget.api, key: ValueKey('opp_${widget.api.baseUrl}')),
      StockScreen(api: widget.api),
      ChatScreen(api: widget.api),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(titles[index]),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () async {
              await Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => SettingsScreen(
                  store: widget.store,
                  onSaved: widget.onSettingsChanged,
                ),
              ));
            },
          ),
        ],
      ),
      body: IndexedStack(index: index, children: pages),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: index,
        onTap: (i) => setState(() => index = i),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_rounded), label: 'Home'),
          BottomNavigationBarItem(icon: Icon(Icons.list_alt_rounded), label: 'Opportunities'),
          BottomNavigationBarItem(icon: Icon(Icons.search_rounded), label: 'Stock'),
          BottomNavigationBarItem(icon: Icon(Icons.chat_bubble_outline_rounded), label: 'AI Chat'),
        ],
      ),
    );
  }
}
