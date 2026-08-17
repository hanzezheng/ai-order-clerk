import 'package:flutter_test/flutter_test.dart';
import 'package:sales_clerk/voice/asr_text.dart';

void main() {
  test('只剥 SenseVoice 标签，不改口令', () {
    expect(
      asrFinalText('<|zh|><|NEUTRAL|><|Speech|>李老板苹果二十箱'),
      '李老板苹果二十箱',
    );
    expect(asrFinalText('老李 富士 二十'), '老李 富士 二十');
    expect(asrFinalText('那个苹果再加十箱'), '那个苹果再加十箱');
    expect(asrFinalText('<|zh|>好了'), '好了');
    expect(asrFinalText('   '), '');
  });
}
