import 'package:flutter_tts/flutter_tts.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_to_text.dart';

import 'speech_ports.dart';

class DeviceSpeechInput implements SpeechInput {
  DeviceSpeechInput({SpeechToText? engine}) : _engine = engine ?? SpeechToText();

  final SpeechToText _engine;
  Future<void>? _startWork;
  var _prepared = false;
  var _buffer = '';

  @override
  var isAvailable = false;

  @override
  String? lastError;

  @override
  Future<void> prepare() async {
    lastError = null;
    final mic = await Permission.microphone.request();
    if (!mic.isGranted) {
      isAvailable = false;
      lastError = '请允许麦克风，才能按住说话。';
      _prepared = true;
      return;
    }
    isAvailable = await _engine.initialize(
      onError: (error) {
        lastError = _mapError(error.errorMsg);
      },
    );
    if (!isAvailable) {
      lastError = '这台手机没有听写。到系统设置打开语音识别，或把这句话打在下面。';
    }
    _prepared = true;
  }

  @override
  Future<void> start({void Function(String partial)? onPartial}) async {
    if (!_prepared) {
      await prepare();
    }
    _buffer = '';
    lastError = null;
    if (!isAvailable) {
      return;
    }
    final work = () async {
      final localeId = await _chineseLocale();
      await _engine.listen(
        onResult: (result) {
          _buffer = result.recognizedWords.trim();
          if (_buffer.isNotEmpty) {
            onPartial?.call(_buffer);
          }
        },
        listenOptions: SpeechListenOptions(
          localeId: localeId,
          partialResults: true,
          cancelOnError: false,
          listenMode: ListenMode.dictation,
          listenFor: const Duration(seconds: 60),
          pauseFor: const Duration(seconds: 8),
        ),
      );
    }();
    _startWork = work;
    await work;
  }

  @override
  Future<String> stop() async {
    final startWork = _startWork;
    if (startWork != null) {
      await startWork;
    }
    _startWork = null;
    if (_engine.isListening) {
      await _engine.stop();
    }
    final text = _buffer.trim();
    if (text.isEmpty && lastError == null) {
      lastError = isAvailable ? '没听清，按住再说，或打在下面。' : '这台手机没有听写。把这句话打在下面。';
    }
    return text;
  }

  Future<String?> _chineseLocale() async {
    final locales = await _engine.locales();
    for (final locale in locales) {
      final id = locale.localeId.toLowerCase();
      if (id.contains('zh') || id.contains('cmn') || id.endsWith('_cn') || id.contains('-cn')) {
        return locale.localeId;
      }
    }
    return locales.isEmpty ? null : locales.first.localeId;
  }

  String _mapError(String code) {
    switch (code) {
      case 'error_permission':
        return '请允许麦克风，才能按住说话。';
      case 'error_network':
      case 'error_network_timeout':
        return '听写要联网。网络通了再按住说。';
      case 'error_speech_timeout':
      case 'error_no_match':
        return '没听清，按住再说，或打在下面。';
      case 'error_audio':
        return '麦克风不可用，换一只再试。';
      default:
        return '这台手机听写失败。把这句话打在下面。';
    }
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
