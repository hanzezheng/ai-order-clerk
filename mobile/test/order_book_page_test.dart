import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sales_clerk/stall/stall_binding.dart';
import 'package:sales_clerk/state/order_book_controller.dart';
import 'package:sales_clerk/ui/order_book_page.dart';
import 'package:sales_clerk/ui/stall_bind_page.dart';
import 'package:sales_clerk/voice/speech_ports.dart';

import 'fake_clerk_api.dart';

void main() {
  testWidgets('档口绑定页只要档口名', (tester) async {
    StallBinding? bound;
    await tester.pumpWidget(
      MaterialApp(
        home: StallBindPage(onBound: (value) async => bound = value),
      ),
    );
    expect(find.text('这个手机绑哪个档口？'), findsOneWidget);
    expect(find.textContaining('客户管理'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, '3号档');
    await tester.tap(find.text('开始开单'));
    await tester.pump();
    expect(bound?.stallName, '3号档');
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

    await controller.submitUtterance('开李老板的单苹果二十箱', source: 'voice');
    await tester.pump();
    expect(find.text('李老板'), findsOneWidget);
    expect(find.text('苹果'), findsOneWidget);
    expect(find.text('80果'), findsOneWidget);
    expect(find.text('20箱'), findsOneWidget);

    await controller.confirmDone();
    await tester.pump();
    expect(find.textContaining('已确认'), findsWidgets);
    expect(find.text('已进草稿'), findsOneWidget);
    expect(find.text('再开一单'), findsOneWidget);
  });
}
