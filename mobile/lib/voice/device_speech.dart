import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_to_text.dart';

import 'speech_ports.dart';

class DeviceSpeechInput implements SpeechInput {
  DeviceSpeechInput({SpeechToText? engine}) : _engine = engine ?? SpeechToText();

  final SpeechToText _engine;
  var _ready = false;
  var _buffer = '';

  Future<void> _ensure() async {
    if (_ready) {
      return;
    }
    _ready = await _engine.initialize();
  }

  @override
  Future<void> start() async {
    await _ensure();
    _buffer = '';
    if (!_ready) {
      return;
    }
    await _engine.listen(
      onResult: (result) {
        _buffer = result.recognizedWords;
      },
      listenOptions: SpeechListenOptions(
        localeId: 'zh_CN',
        partialResults: true,
      ),
    );
  }

  @override
  Future<String> stop() async {
    if (_ready) {
      await _engine.stop();
    }
    return _buffer.trim();
  }
}

class DeviceSpeechOutput implements SpeechOutput {
  DeviceSpeechOutput({FlutterTts? tts}) : _tts = tts ?? FlutterTts();

  final FlutterTts _tts;

  @override
  Future<void> speak(String replyText) async {
    final text = replyText.trim();
    if (text.isEmpty) {
      return;
    }
    await _tts.setLanguage('zh-CN');
    await _tts.speak(text);
  }
}
