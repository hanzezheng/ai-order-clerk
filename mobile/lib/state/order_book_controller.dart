import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';

import '../api/clerk_api.dart';
import '../api/models.dart';
import '../stall/stall_binding.dart';
import '../voice/speech_ports.dart';

enum BookPhase { idle, listening, processing, done }

class OrderBookController extends ChangeNotifier {
  OrderBookController({
    required this.api,
    required this.stall,
    required this.speech,
    required this.tts,
    Uuid? uuid,
  }) : _uuid = uuid ?? const Uuid();

  final ClerkApi api;
  StallBinding stall;
  final SpeechInput speech;
  final SpeechOutput tts;
  final Uuid _uuid;

  BookPhase phase = BookPhase.idle;
  WorkbenchSnapshot book = const WorkbenchSnapshot(businessDate: '');
  DraftOrder? currentDraft;
  String replyText = '';
  String errorText = '';
  String overlay = '';
  var offline = false;
  int _seq = 0;
  int _holdEpoch = 0;

  String? get currentSessionId => book.currentSessionId;

  String get currentStatusLabel {
    final draft = currentDraft;
    if (draft == null || draft.isEmpty) {
      return '还没有开始开单';
    }
    if (draft.isConfirmed) {
      final posting = book.current?.posting;
      final label = postingLabel(posting);
      return label.isEmpty ? '已确认' : '已确认 · $label';
    }
    return '待确认';
  }

  Future<void> bootstrap() async {
    errorText = '';
    offline = false;
    notifyListeners();
    await speech.prepare();
    try {
      await refresh();
      if (currentSessionId == null) {
        await startNextOrder();
      } else {
        await _loadCurrentDraft();
      }
    } catch (_) {
      offline = true;
      errorText = '电脑上的开单服务还没打开。打开后再试。';
      notifyListeners();
      return;
    }
    if (!speech.isAvailable && (speech.lastError ?? '').isNotEmpty) {
      errorText = speech.lastError!;
      notifyListeners();
    }
  }

  Future<void> refresh() async {
    book = await api.getWorkbench();
    notifyListeners();
  }

  Future<void> startNextOrder({bool keepListening = false}) async {
    errorText = '';
    book = await api.createTask();
    _seq = 0;
    replyText = '';
    overlay = '';
    if (!keepListening) {
      phase = BookPhase.idle;
    }
    await _loadCurrentDraft();
  }

  Future<void> selectPending(String sessionId) async {
    book = await api.setCurrent(sessionId);
    _seq = 0;
    phase = BookPhase.idle;
    await _loadCurrentDraft();
  }

  Future<void> beginHold() async {
    if (phase == BookPhase.processing || offline) {
      return;
    }
    final epoch = ++_holdEpoch;
    if (phase == BookPhase.done || (currentDraft?.isConfirmed ?? false) || currentSessionId == null) {
      await startNextOrder(keepListening: true);
    }
    if (epoch != _holdEpoch) {
      return;
    }
    errorText = '';
    overlay = '';
    phase = BookPhase.listening;
    notifyListeners();
    if (!speech.isAvailable) {
                    errorText = speech.lastError ?? '听写还没准备好。把这句话打在下面。';
      phase = BookPhase.idle;
      notifyListeners();
      return;
    }
    await speech.start(
      onPartial: (partial) {
        if (epoch != _holdEpoch || phase != BookPhase.listening) {
          return;
        }
        overlay = partial;
        notifyListeners();
      },
    );
    if (epoch != _holdEpoch) {
      await speech.stop();
    }
  }

  Future<void> endHold() async {
    if (phase != BookPhase.listening) {
      _holdEpoch++;
      return;
    }
    _holdEpoch++;
    overlay = '正在听成字…';
    notifyListeners();
    final text = (await speech.stop()).trim();
    overlay = text;
    notifyListeners();
    if (text.isEmpty) {
      errorText = speech.lastError ?? '没听清，按住再说。';
      phase = BookPhase.idle;
      notifyListeners();
      return;
    }
    await submitUtterance(text, source: 'voice');
  }

  Future<void> confirmDone() async {
    await submitUtterance('好了', source: 'text');
  }

  Future<void> submitTyped(String raw) async {
    if (phase == BookPhase.processing) {
      return;
    }
    await submitUtterance(raw, source: 'text');
  }

  Future<void> submitUtterance(String raw, {required String source}) async {
    final text = raw.trim();
    if (text.isEmpty) {
      return;
    }
    if (currentSessionId == null || (currentDraft?.isConfirmed ?? false)) {
      await startNextOrder();
    }
    final sessionId = currentSessionId;
    if (sessionId == null) {
      errorText = '还没有当前单';
      notifyListeners();
      return;
    }
    phase = BookPhase.processing;
    errorText = '';
    notifyListeners();
    try {
      _seq += 1;
      final result = await api.postTurn(
        sessionId: sessionId,
        text: text,
        seq: _seq,
        utteranceId: _uuid.v4(),
        source: source,
        expectMore: expectMoreFor(text),
      );
      replyText = result.replyText;
      currentDraft = result.draft;
      await refresh();
      await _loadCurrentDraft();
      if (result.confirmOk || (currentDraft?.isConfirmed ?? false)) {
        phase = BookPhase.done;
      } else {
        phase = BookPhase.idle;
      }
      notifyListeners();
      await tts.speak(replyText);
    } on ClerkApiException catch (err) {
      _seq -= 1;
      if (err.statusCode == 409 && err.body.contains('task_completed')) {
        errorText = '这张已经好了，请再开一单';
        phase = BookPhase.done;
      } else {
        errorText = '这一句没写上，再喊一次';
        phase = BookPhase.idle;
      }
      notifyListeners();
    } catch (_) {
      _seq -= 1;
      errorText = '网络不行，先别猜，再试一次';
      phase = BookPhase.idle;
      notifyListeners();
    }
  }

  Future<void> _loadCurrentDraft() async {
    final sessionId = currentSessionId;
    if (sessionId == null) {
      currentDraft = null;
      notifyListeners();
      return;
    }
    final snap = await api.getSession(sessionId);
    currentDraft = snap.draft;
    notifyListeners();
  }
}
