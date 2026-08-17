import 'package:flutter_test/flutter_test.dart';
import 'package:sales_clerk/api/discovery.dart';

class _FakeHealth implements HealthProbe {
  _FakeHealth(this.good);
  final Set<String> good;
  @override
  Future<bool> ok(String apiBase) async => good.contains(apiBase);
}

class _FakePresence implements PresenceLookup {
  _FakePresence(this.urls);
  final List<String> urls;
  var called = false;
  @override
  Future<List<String>> discover() async {
    called = true;
    return urls;
  }
}

void main() {
  test('健康检查命中种子地址，不去翻局域网', () async {
    final udp = _FakePresence(['http://192.168.1.8:8000']);
    final finder = LanClerkFinder(
      seeds: const ['http://127.0.0.1:8000', 'http://10.0.2.2:8000'],
      health: _FakeHealth({'http://10.0.2.2:8000'}),
      presence: udp,
    );
    expect(await finder.find(), 'http://10.0.2.2:8000');
    expect(udp.called, isFalse);
  });

  test('种子都没有时用局域网发现的地址', () async {
    final finder = LanClerkFinder(
      seeds: const ['http://127.0.0.1:8000'],
      health: _FakeHealth({'http://192.168.1.8:8000'}),
      presence: _FakePresence(const ['http://192.168.1.8:8000']),
    );
    expect(await finder.find(), 'http://192.168.1.8:8000');
  });

  test('什么都找不到就返回空，不编地址', () async {
    final finder = LanClerkFinder(
      seeds: const ['http://127.0.0.1:8000'],
      health: _FakeHealth({}),
      presence: _FakePresence(const []),
    );
    expect(await finder.find(), isNull);
  });
}
