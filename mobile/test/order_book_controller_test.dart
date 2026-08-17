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

  test('松开没有字时提示，不假装开单', () async {
    final api = FakeClerkApi();
    final controller = OrderBookController(
      api: api,
      stall: const StallBinding(stallName: '3号档', apiBase: 'http://127.0.0.1:8000'),
      speech: SilentSpeechInput(),
      tts: SilentSpeechOutput(),
    );
    await controller.bootstrap();
    await controller.beginHold();
    await controller.endHold();
    expect(api.turns, isEmpty);
    expect(controller.errorText, contains('没听清'));
    expect(controller.phase, BookPhase.idle);
  });

  test('听写不可用时不假装开单', () async {
    final api = FakeClerkApi();
    final speech = SilentSpeechInput()
      ..isAvailable = false
      ..lastError = '听写还没准备好。把这句话打在下面。';
    final controller = OrderBookController(
      api: api,
      stall: const StallBinding(stallName: '3号档', apiBase: 'http://127.0.0.1:8000'),
      speech: speech,
      tts: SilentSpeechOutput(),
    );
    await controller.bootstrap();
    expect(controller.errorText, contains('听写'));
    await controller.beginHold();
    expect(controller.phase, BookPhase.idle);
    expect(api.turns, isEmpty);
  });

  test('听不清可以打同一句提交', () async {
    final api = FakeClerkApi();
    final controller = OrderBookController(
      api: api,
      stall: const StallBinding(stallName: '3号档', apiBase: 'http://127.0.0.1:8000'),
      speech: SilentSpeechInput(),
      tts: SilentSpeechOutput(),
    );
    await controller.bootstrap();
    await controller.submitTyped('开李老板的单苹果二十箱');
    expect(api.turns, ['开李老板的单苹果二十箱']);
    expect(controller.currentDraft!.customer!.displayName, '李老板');
  });
}
