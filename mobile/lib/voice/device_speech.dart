import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/services.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import 'package:sherpa_onnx/sherpa_onnx.dart' as sherpa;

import 'asr_text.dart';
import 'speech_ports.dart';

/// 端侧 SenseVoice。一段按住 → 一条 final 文本。不依赖系统听写，不改 Runtime。
class DeviceSpeechInput implements SpeechInput {
  DeviceSpeechInput({AudioRecorder? recorder}) : _recorder = recorder ?? AudioRecorder();

  final AudioRecorder _recorder;
  sherpa.OfflineRecognizer? _recognizer;
  Future<void>? _startWork;
  var _prepared = false;
  static const _sampleRate = 16000;

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
    try {
      sherpa.initBindings();
      final modelDir = await _ensureModel();
      _recognizer?.free();
      _recognizer = sherpa.OfflineRecognizer(
        sherpa.OfflineRecognizerConfig(
          model: sherpa.OfflineModelConfig(
            senseVoice: sherpa.OfflineSenseVoiceModelConfig(
              model: p.join(modelDir, 'model.int8.onnx'),
              language: '',
              useInverseTextNormalization: true,
            ),
            tokens: p.join(modelDir, 'tokens.txt'),
            numThreads: 2,
            debug: false,
            provider: 'cpu',
          ),
        ),
      );
      isAvailable = true;
    } catch (_) {
      isAvailable = false;
      lastError = '听写还没准备好。请再打开一次，或把这句话打在下面。';
    }
    _prepared = true;
  }

  @override
  Future<void> start({void Function(String partial)? onPartial}) async {
    if (!_prepared) {
      await prepare();
    }
    lastError = null;
    if (!isAvailable) {
      return;
    }
    final work = () async {
      final dir = await getTemporaryDirectory();
      final path = p.join(dir.path, 'hold.pcm');
      final file = File(path);
      if (await file.exists()) {
        await file.delete();
      }
      await _recorder.start(
        RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: _sampleRate,
          numChannels: 1,
          echoCancel: true,
          noiseSuppress: true,
          androidConfig: const AndroidRecordConfig(
            useLegacy: false,
            audioSource: AndroidAudioSource.mic,
            manageBluetooth: false,
          ),
        ),
        path: path,
      );
      onPartial?.call('正在听…');
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
    String path = '';
    try {
      path = (await _recorder.stop()) ?? '';
    } catch (_) {
      path = '';
    }
    if (path.isEmpty) {
      lastError ??= '没听清，按住再说。';
      return '';
    }
    final recognizer = _recognizer;
    if (recognizer == null) {
      lastError = '听写还没准备好。请再打开一次。';
      return '';
    }
    try {
      final samples = await _pcm16ToFloat(path);
      if (samples.length < _sampleRate ~/ 5) {
        lastError = '按太短了，按住再说。';
        return '';
      }
      final stream = recognizer.createStream();
      stream.acceptWaveform(samples: samples, sampleRate: _sampleRate);
      recognizer.decode(stream);
      final text = asrFinalText(recognizer.getResult(stream).text);
      stream.free();
      if (text.isEmpty) {
        lastError = '没听清，按住再说。';
      }
      return text;
    } catch (_) {
      lastError = '这一句没听成字，按住再说。';
      return '';
    }
  }

  Future<String> _ensureModel() async {
    final root = await getApplicationSupportDirectory();
    final dir = Directory(p.join(root.path, 'asr'));
    await dir.create(recursive: true);
    await _copyAsset('assets/asr/tokens.txt', File(p.join(dir.path, 'tokens.txt')));
    final onnx = File(p.join(dir.path, 'model.int8.onnx'));
    if (!await onnx.exists() || await onnx.length() < 1024 * 1024) {
      await _copyAsset('assets/asr/model.int8.onnx', onnx);
    }
    if (!await onnx.exists() || await onnx.length() < 1024 * 1024) {
      throw StateError('missing sensevoice model');
    }
    return dir.path;
  }

  Future<void> _copyAsset(String asset, File dest) async {
    if (await dest.exists() && await dest.length() > 0) {
      return;
    }
    final data = await rootBundle.load(asset);
    await dest.writeAsBytes(data.buffer.asUint8List(), flush: true);
  }

  Future<Float32List> _pcm16ToFloat(String path) async {
    final bytes = await File(path).readAsBytes();
    final even = bytes.length - (bytes.length % 2);
    final samples = Float32List(even ~/ 2);
    final data = ByteData.sublistView(bytes, 0, even);
    for (var i = 0; i < samples.length; i++) {
      samples[i] = data.getInt16(i * 2, Endian.little) / 32768.0;
    }
    return samples;
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
