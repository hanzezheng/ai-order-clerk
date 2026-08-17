abstract class SpeechInput {
  Future<void> start();
  Future<String> stop();
}

abstract class SpeechOutput {
  Future<void> speak(String replyText);
}

class SilentSpeechInput implements SpeechInput {
  String transcript = '';

  @override
  Future<void> start() async {}

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
