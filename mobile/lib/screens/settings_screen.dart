import 'package:flutter/material.dart';
import '../api.dart';
import '../settings_store.dart';
import '../theme.dart';

class SettingsScreen extends StatefulWidget {
  final SettingsStore store;
  final bool isLogin;
  final VoidCallback onSaved;
  const SettingsScreen({super.key, required this.store, required this.onSaved, this.isLogin = false});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final baseCtl = TextEditingController();
  final keyCtl = TextEditingController();
  String status = '';
  bool testing = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    baseCtl.text = await widget.store.getBaseUrl();
    keyCtl.text = await widget.store.getApiKey();
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    baseCtl.dispose();
    keyCtl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    await widget.store.save(baseCtl.text, keyCtl.text);
    setState(() => status = 'Saved.');
    widget.onSaved();
  }

  Future<void> _test() async {
    await widget.store.save(baseCtl.text, keyCtl.text);
    setState(() {
      testing = true;
      status = '';
    });
    final api = ApiService(baseUrl: baseCtl.text.trim(), apiKey: keyCtl.text.trim());
    try {
      final h = await api.health();
      await api.signal(); // validates the key too
      setState(() => status = 'Connected ✓  (${h['service']} v${h['version']})');
      widget.onSaved();
    } on ApiException catch (e) {
      setState(() => status = 'Failed: ${e.message}');
    } finally {
      setState(() => testing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final body = ListView(
      padding: const EdgeInsets.all(20),
      children: [
        if (widget.isLogin) ...[
          const Text('PSX AI Scanner',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900)),
          const Text('Connect to your scanner backend to begin.',
              style: TextStyle(color: AppColors.muted)),
          const SizedBox(height: 20),
        ],
        const Text('API base URL', style: TextStyle(color: AppColors.muted, fontSize: 12)),
        const SizedBox(height: 6),
        TextField(controller: baseCtl, decoration: const InputDecoration(hintText: 'http://192.168.x.x:8000')),
        const SizedBox(height: 16),
        const Text('API key (X-API-Key)', style: TextStyle(color: AppColors.muted, fontSize: 12)),
        const SizedBox(height: 6),
        TextField(controller: keyCtl, obscureText: true, decoration: const InputDecoration(hintText: 'psx-dev-key-change-me')),
        const SizedBox(height: 18),
        Row(
          children: [
            FilledButton(onPressed: _save, child: const Text('Save')),
            const SizedBox(width: 12),
            OutlinedButton(
              onPressed: testing ? null : _test,
              child: Text(testing ? 'Testing…' : 'Test connection'),
            ),
          ],
        ),
        if (status.isNotEmpty) ...[
          const SizedBox(height: 16),
          Text(status, style: const TextStyle(color: AppColors.muted)),
        ],
        const SizedBox(height: 20),
        const Text(
          'The key is stored in this device\'s secure storage (Keychain / EncryptedSharedPreferences). '
          'The backend runs on your PC — the phone must be on the same WiFi, or the API deployed remotely.',
          style: TextStyle(color: AppColors.muted, fontSize: 12),
        ),
      ],
    );

    if (widget.isLogin) {
      return Scaffold(appBar: AppBar(title: const Text('Setup')), body: body);
    }
    return Scaffold(appBar: AppBar(title: const Text('Settings')), body: body);
  }
}
