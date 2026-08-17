import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sales_clerk/api/discovery.dart';
import 'package:sales_clerk/stall/stall_binding.dart';
import 'package:sales_clerk/state/order_book_controller.dart';
import 'package:sales_clerk/ui/launch_page.dart';
import 'package:sales_clerk/ui/order_book_page.dart';
import 'package:sales_clerk/ui/stall_bind_page.dart';
import 'package:sales_clerk/voice/speech_ports.dart';

import 'fake_clerk_api.dart';

class _FakeHealth implements HealthProbe {
  _FakeHealth(this.good);
  final Set<String> good;
  @override
  Future<bool> ok(String apiBase) async => good.contains(apiBase);
}

class _FakePresence implements PresenceLookup {
  _FakePresence(this.urls);
  final List<String> urls;
  @override
  Future<List<String>> discover() async => urls;
}

void main() {
  testWidgets('档口绑定页只要档口名', (tester) async {
    StallBinding? bound;
    await tester.pumpWidget(
      MaterialApp(
        home: StallBindPage(
          apiBase: 'http://127.0.0.1:8000',
          onBound: (value) async => bound = value,
        ),
      ),
    );
    expect(find.text('这个手机帮哪个档口开单？'), findsOneWidget);
    expect(find.text('开单服务地址'), findsNothing);
    await tester.enterText(find.byType(TextField), '3号档');
    await tester.tap(find.text('开始开单'));
    await tester.pump();
    expect(bound?.stallName, '3号档');
    expect(bound?.apiBase, 'http://127.0.0.1:8000');
  });

  testWidgets('找到服务后只问档口名', (tester) async {
    StallBinding? bound;
    await tester.pumpWidget(
      MaterialApp(
        home: LaunchPage(
          finder: LanClerkFinder(
            seeds: const ['http://127.0.0.1:8000'],
            health: _FakeHealth({'http://127.0.0.1:8000'}),
            presence: _FakePresence(const []),
          ),
          onBound: (value) async => bound = value,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('这个手机帮哪个档口开单？'), findsOneWidget);
    expect(find.text('开单服务地址'), findsNothing);
    expect(bound, isNull);
  });

  testWidgets('找不到服务时不假装能开单', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: LaunchPage(
          finder: LanClerkFinder(
            seeds: const ['http://127.0.0.1:8000'],
            health: _FakeHealth({}),
            presence: _FakePresence(const []),
          ),
          onBound: (_) async {},
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('开单服务还没打开'), findsOneWidget);
    expect(find.text('再找一次'), findsOneWidget);
    expect(find.text('开始开单'), findsNothing);
  });

  testWidgets('今日开单本能看见当前单和好了', (tester) async {
    final controller = OrderBookController(
      api: FakeClerkApi(),
      stall: const StallBinding(stallName: '3号档', apiBase: 'http://127.0.0.1:8000'),
      speech: SilentSpeechInput(),
      tts: SilentSpeechOutput(),
    );
    await tester.pumpWidget(MaterialApp(home: OrderBookPage(controller: controller)));
    await tester.pumpAndSettle();
    expect(find.text('今日开单'), findsOneWidget);
    expect(find.text('当前订单'), findsOneWidget);
    expect(find.text('还没有开始开单'), findsWidgets);
    expect(find.text('按住说话'), findsOneWidget);
    expect(find.text('好了'), findsOneWidget);
    expect(find.text('库存'), findsNothing);
    expect(find.text('收款'), findsNothing);
    expect(find.text('听不清就打这句'), findsOneWidget);

    await controller.submitUtterance('开李老板的单苹果二十箱', source: 'voice');
    await tester.pump();
    expect(find.text('李老板'), findsOneWidget);
    expect(find.text('苹果'), findsOneWidget);
    expect(find.text('80果'), findsOneWidget);
    expect(find.text('20箱'), findsOneWidget);

    await controller.confirmDone();
    await tester.pump();
    expect(controller.currentStatusLabel, contains('已进草稿'));
    expect(find.textContaining('已确认'), findsWidgets);
    expect(find.textContaining('已进草稿'), findsWidgets);
    expect(find.text('再开一单'), findsOneWidget);
  });

  testWidgets('服务不在时只让再试，不露出开单台', (tester) async {
    final controller = OrderBookController(
      api: DownClerkApi(),
      stall: const StallBinding(stallName: '3号档', apiBase: 'http://127.0.0.1:8000'),
      speech: SilentSpeechInput(),
      tts: SilentSpeechOutput(),
    );
    await tester.pumpWidget(MaterialApp(home: OrderBookPage(controller: controller)));
    await tester.pumpAndSettle();
    expect(find.textContaining('开单服务还没打开'), findsOneWidget);
    expect(find.text('再试一次'), findsOneWidget);
    expect(find.text('按住说话'), findsNothing);
    expect(find.text('好了'), findsNothing);
  });
}
