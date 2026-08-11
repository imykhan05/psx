import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Persists the API base URL and key in platform secure storage
/// (Keychain on iOS, EncryptedSharedPreferences on Android).
class SettingsStore {
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );
  static const _kBase = 'psx_api_base';
  static const _kKey = 'psx_api_key';

  static const defaultBase = 'http://10.0.2.2:8000'; // Android emulator -> host PC

  Future<String> getBaseUrl() async =>
      (await _storage.read(key: _kBase)) ?? defaultBase;

  Future<String> getApiKey() async => (await _storage.read(key: _kKey)) ?? '';

  Future<void> save(String baseUrl, String apiKey) async {
    await _storage.write(key: _kBase, value: baseUrl.trim());
    await _storage.write(key: _kKey, value: apiKey.trim());
  }
}
