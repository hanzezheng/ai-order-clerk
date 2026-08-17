import 'package:flutter_test/flutter_test.dart';
import 'package:sales_clerk/stall/stall_binding.dart';
import 'package:sales_clerk/state/order_book_controller.dart';
import 'package:sales_clerk/voice/speech_ports.dart';

import 'fake_clerk_api.dart';

void main() {
  test('打开、喊第一单、改量、好了、今日本出现已确认', () async {
    final api = FakeClerkApi();
    final speech = SilentSpeechInput();
    final tts = SilentSpeechOutput();
    final controller = OrderBookController(
      api: api,
      stall: const StallBinding(stallName: '3号档', apiBase: 'http://127.0.0.1:8000'),
      speech: speech,
      tts: tts,
    );

    await controller.bootstrap();
    expect(controller.currentStatusLabel, '还没有开始开单');
    expect(controller.book.todayCount, 0);

    await controller.submitUtterance('开李老板的单苹果二十箱', source: 'voice');
    expect(controller.currentDraft!.customer!.displayName, '李老板');
    expect(controller.currentDraft!.lines.single.product, '苹果');
    expect(controller.currentDraft!.lines.single.spec, '80果');
    expect(controller.currentDraft!.lines.single.qtyText, '20箱');
    expect(controller.currentStatusLabel, '待确认');
    expect(tts.spoken.last, contains('李老板'));

    await controller.submitUtterance('苹果改30箱', source: 'voice');
    expect(controller.currentDraft!.lines.single.qtyText, '30箱');
    expect(controller.currentDraft!.isConfirmed, isFalse);

    await controller.confirmDone();
    expect(controller.currentDraft!.isConfirmed, isTrue);
    expect(controller.book.confirmed.single.customerLabel, '李老板');
    expect(controller.book.confirmed.single.posting, 'posted');
    expect(controller.book.todayCount, 1);
    expect(api.turns, ['开李老板的单苹果二十箱', '苹果改30箱', '好了']);
    expect(tts.spoken.last, contains('价未定'));
  });

  test('按住说话把设备字以 voice 提交', () async {
    final api = FakeClerkApi();
    final speech = SilentSpeechInput()..transcript = '开李老板的单苹果二十箱';
    final controller = OrderBookController(
      api: api,
      stall: const StallBinding(stallName: '3号档', apiBase: 'http://127.0.0.1:8000'),
      speech: speech,
      tts: SilentSpeechOutput(),
    );

    await controller.bootstrap();
    await controller.beginHold();
    expect(controller.phase, BookPhase.listening);
    await controller.endHold();
    expect(api.turns, ['开李老板的单苹果二十箱']);
    expect(controller.currentDraft!.customer!.displayName, '李老板');
    expect(controller.phase, BookPhase.idle);
  });
}
