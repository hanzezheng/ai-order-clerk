import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models.dart';

class ClerkApiException implements Exception {
  ClerkApiException(this.statusCode, this.body);

  final int statusCode;
  final String body;

  @override
  String toString() => 'ClerkApiException($statusCode, $body)';
}

abstract class ClerkApi {
  Future<WorkbenchSnapshot> getWorkbench();
  Future<WorkbenchSnapshot> createTask();
  Future<WorkbenchSnapshot> setCurrent(String sessionId);
  Future<SessionSnapshot> getSession(String sessionId);
  Future<TurnResult> postTurn({
    required String sessionId,
    required String text,
    required int seq,
    required String utteranceId,
    String source = 'text',
    bool expectMore = true,
  });
}

class HttpClerkApi implements ClerkApi {
  HttpClerkApi({required this.baseUrl, http.Client? client}) : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  Uri _uri(String path) {
    final root = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
    return Uri.parse('$root$path');
  }

  Future<Map<String, dynamic>> _send(
    String method,
    String path, {
    Map<String, dynamic>? body,
    int success = 200,
  }) async {
    final uri = _uri(path);
    final headers = {'Content-Type': 'application/json; charset=utf-8'};
    final encoded = body == null ? null : jsonEncode(body);
    late http.Response response;
    switch (method) {
      case 'GET':
        response = await _client.get(uri, headers: headers);
      case 'POST':
        response = await _client.post(uri, headers: headers, body: encoded);
      default:
        throw ArgumentError(method);
    }
    if (response.statusCode != success) {
      throw ClerkApiException(response.statusCode, response.body);
    }
    final decoded = jsonDecode(utf8.decode(response.bodyBytes));
    if (decoded is! Map<String, dynamic>) {
      throw ClerkApiException(response.statusCode, response.body);
    }
    return decoded;
  }

  @override
  Future<WorkbenchSnapshot> getWorkbench() async {
    return WorkbenchSnapshot.fromJson(await _send('GET', '/v1/workbench'));
  }

  @override
  Future<WorkbenchSnapshot> createTask() async {
    final json = await _send('POST', '/v1/workbench/tasks', success: 201);
    return WorkbenchSnapshot.fromJson(json);
  }

  @override
  Future<WorkbenchSnapshot> setCurrent(String sessionId) async {
    return WorkbenchSnapshot.fromJson(
      await _send('POST', '/v1/workbench/current', body: {'session_id': sessionId}),
    );
  }

  @override
  Future<SessionSnapshot> getSession(String sessionId) async {
    return SessionSnapshot.fromJson(await _send('GET', '/v1/sessions/$sessionId'));
  }

  @override
  Future<TurnResult> postTurn({
    required String sessionId,
    required String text,
    required int seq,
    required String utteranceId,
    String source = 'text',
    bool expectMore = true,
  }) async {
    return TurnResult.fromJson(
      await _send(
        'POST',
        '/v1/sessions/$sessionId/turns',
        body: {
          'text': text,
          'source': source,
          'utterance_id': utteranceId,
          'seq': seq,
          'is_final': true,
          'expect_more': expectMore,
        },
      ),
    );
  }
}
