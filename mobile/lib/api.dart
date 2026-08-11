import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

/// A failure with a human-readable message. `isConnection` distinguishes
/// "can't reach the server" (wrong URL / not on same WiFi / backend down)
/// from an HTTP-level error, so the UI can show a dedicated not-connected state.
class ApiException implements Exception {
  final String message;
  final bool isConnection;
  final int? status;
  ApiException(this.message, {this.isConnection = false, this.status});
  @override
  String toString() => message;
}

class ApiService {
  final String baseUrl;
  final String apiKey;
  ApiService({required this.baseUrl, required this.apiKey});

  Map<String, String> get _headers => {
        'X-API-Key': apiKey,
        'Content-Type': 'application/json',
      };

  Uri _uri(String path) => Uri.parse('${baseUrl.replaceAll(RegExp(r"/+$"), "")}$path');

  Future<dynamic> _get(String path, {Duration timeout = const Duration(seconds: 15)}) async {
    try {
      final res = await http.get(_uri(path), headers: _headers).timeout(timeout);
      return _decode(res);
    } on TimeoutException {
      throw ApiException('Request timed out. Is the backend reachable?', isConnection: true);
    } on SocketException {
      throw ApiException('Cannot reach the API. Check the base URL and that your phone is on the same network.', isConnection: true);
    } on http.ClientException {
      throw ApiException('Cannot reach the API. Check the base URL and that your phone is on the same network.', isConnection: true);
    }
  }

  Future<dynamic> _post(String path, Map<String, dynamic> body,
      {Duration timeout = const Duration(seconds: 60)}) async {
    try {
      final res = await http
          .post(_uri(path), headers: _headers, body: jsonEncode(body))
          .timeout(timeout);
      return _decode(res);
    } on TimeoutException {
      throw ApiException('Request timed out.', isConnection: true);
    } on SocketException {
      throw ApiException('Cannot reach the API. Check the base URL and that your phone is on the same network.', isConnection: true);
    } on http.ClientException {
      throw ApiException('Cannot reach the API. Check the base URL and that your phone is on the same network.', isConnection: true);
    }
  }

  dynamic _decode(http.Response res) {
    dynamic data;
    try {
      data = res.body.isNotEmpty ? jsonDecode(res.body) : null;
    } catch (_) {
      data = null;
    }
    if (res.statusCode >= 200 && res.statusCode < 300) return data;

    // The API returns clean {"error","detail"} bodies — surface the detail.
    String detail = 'Request failed (HTTP ${res.statusCode}).';
    if (data is Map && data['detail'] != null) {
      detail = data['detail'].toString();
    } else if (data is Map && data['error'] != null) {
      detail = data['error'].toString();
    }
    throw ApiException(detail, status: res.statusCode);
  }

  Future<Map<String, dynamic>> health() async =>
      Map<String, dynamic>.from(await _get('/health'));

  Future<Map<String, dynamic>> signal() async =>
      Map<String, dynamic>.from(await _get('/signal'));

  Future<List<dynamic>> opportunities({int limit = 100}) async {
    final data = await _get('/opportunities?limit=$limit');
    return List<dynamic>.from((data as Map)['opportunities'] ?? []);
  }

  Future<Map<String, dynamic>> stock(String ticker) async =>
      Map<String, dynamic>.from(await _get('/stock/${Uri.encodeComponent(ticker)}'));

  Future<String> query(String question) async {
    final data = await _post('/query', {'question': question});
    return (data as Map)['answer']?.toString() ?? '';
  }
}
