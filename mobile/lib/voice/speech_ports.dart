abstract class SpeechInput {
  bool get isAvailable;
  String? get lastError;

  Future<void> prepare();
  Future<void> start({void Function(String partial)? onPartial});
  Future<String> stop();
}

abstract class SpeechOutput {
  Future<void> speak(String replyText);
}

class SilentSpeechInput implements SpeechInput {
  String transcript = '';
  @override
  bool isAvailable = true;
  @override
  String? lastError;

  @override
  Future<void> prepare() async {}

  @override
  Future<void> start({void Function(String partial)? onPartial}) async {
    if (transcript.isNotEmpty) {
      onPartial?.call(transcript);
    }
  }

  @override
  Future<String> stop() async => transcript;
}

class SilentSpeechOutput implements SpeechOutput {
  final spoken = <String>[];

  @override
  Future<void> speak(String replyText) async {
    final text = replyText.trim();
    if (text.isEmpty) {
      return;
    }
    spoken.add(text);
  }
}
