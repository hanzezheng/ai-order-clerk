import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

const presencePort = 38471;
const presenceProbe = 'ai-order-clerk/1?';

abstract class HealthProbe {
  Future<bool> ok(String apiBase);
}

abstract class PresenceLookup {
  Future<List<String>> discover();
}

class HttpHealthProbe implements HealthProbe {
  HttpHealthProbe({http.Client? client, this.timeout = const Duration(milliseconds: 900)})
      : _client = client ?? http.Client();

  final http.Client _client;
  final Duration timeout;

  @override
  Future<bool> ok(String apiBase) async {
    final root = apiBase.endsWith('/') ? apiBase.substring(0, apiBase.length - 1) : apiBase;
    try {
      final response = await _client.get(Uri.parse('$root/health')).timeout(timeout);
      if (response.statusCode != 200) {
        return false;
      }
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      return decoded is Map && decoded['ok'] == true;
    } catch (_) {
      return false;
    }
  }
}

class UdpPresenceLookup implements PresenceLookup {
  UdpPresenceLookup({this.timeout = const Duration(milliseconds: 1600)});

  final Duration timeout;

  @override
  Future<List<String>> discover() async {
    final urls = <String>{};
    late final RawDatagramSocket socket;
    try {
      socket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
    } catch (_) {
      return const [];
    }
    socket.broadcastEnabled = true;
    final payload = utf8.encode(presenceProbe);
    socket.send(payload, InternetAddress('255.255.255.255'), presencePort);
    try {
      socket.send(payload, InternetAddress('10.0.2.2'), presencePort);
    } catch (_) {}
    try {
      socket.send(payload, InternetAddress.loopbackIPv4, presencePort);
    } catch (_) {}
    final done = Completer<void>();
    final timer = Timer(timeout, () {
      if (!done.isCompleted) {
        done.complete();
      }
    });
    socket.listen((event) {
      if (event != RawSocketEvent.read) {
        return;
      }
      final datagram = socket.receive();
      if (datagram == null) {
        return;
      }
      for (final url in _urlsFrom(datagram.data)) {
        urls.add(url);
      }
    });
    await done.future;
    timer.cancel();
    socket.close();
    return urls.toList();
  }
}

List<String> _urlsFrom(List<int> data) {
  try {
    final decoded = jsonDecode(utf8.decode(data));
    if (decoded is! Map) {
      return const [];
    }
    if (decoded['service'] != 'ai-order-clerk') {
      return const [];
    }
    return [
      for (final item in (decoded['urls'] as List? ?? const []))
        if (item is String && item.startsWith('http')) item,
    ];
  } catch (_) {
    return const [];
  }
}

class LanClerkFinder {
  LanClerkFinder({
    required this.seeds,
    HealthProbe? health,
    PresenceLookup? presence,
  })  : health = health ?? HttpHealthProbe(),
        presence = presence ?? UdpPresenceLookup();

  final List<String> seeds;
  final HealthProbe health;
  final PresenceLookup presence;

  Future<String?> find() async {
    final tried = <String>{};
    for (final seed in seeds) {
      final url = _norm(seed);
      if (url.isEmpty || tried.contains(url)) {
        continue;
      }
      tried.add(url);
      if (await health.ok(url)) {
        return url;
      }
    }
    for (final found in await presence.discover()) {
      final url = _norm(found);
      if (url.isEmpty || tried.contains(url)) {
        continue;
      }
      tried.add(url);
      if (await health.ok(url)) {
        return url;
      }
    }
    return null;
  }
}

String _norm(String raw) {
  var value = raw.trim();
  if (value.endsWith('/')) {
    value = value.substring(0, value.length - 1);
  }
  return value;
}

List<String> clerkSeedBases({String defaultApiBase = 'http://127.0.0.1:8000'}) {
  return {
    defaultApiBase,
    'http://127.0.0.1:8000',
    'http://10.0.2.2:8000',
  }.toList();
}
