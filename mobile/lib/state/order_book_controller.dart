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
  int _seq = 0;

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
    await refresh();
    if (currentSessionId == null) {
      await startNextOrder();
    } else {
      await _loadCurrentDraft();
    }
  }

  Future<void> refresh() async {
    book = await api.getWorkbench();
    notifyListeners();
  }

  Future<void> startNextOrder() async {
    errorText = '';
    book = await api.createTask();
    _seq = 0;
    replyText = '';
    overlay = '';
    phase = BookPhase.idle;
    await _loadCurrentDraft();
  }

  Future<void> selectPending(String sessionId) async {
    book = await api.setCurrent(sessionId);
    _seq = 0;
    phase = BookPhase.idle;
    await _loadCurrentDraft();
  }

  Future<void> beginHold() async {
    if (phase == BookPhase.processing) {
      return;
    }
    if (phase == BookPhase.done || (currentDraft?.isConfirmed ?? false)) {
      await startNextOrder();
    }
    errorText = '';
    overlay = '';
    phase = BookPhase.listening;
    notifyListeners();
    await speech.start();
  }

  Future<void> endHold() async {
    if (phase != BookPhase.listening) {
      return;
    }
    final text = (await speech.stop()).trim();
    overlay = text;
    notifyListeners();
    if (text.isEmpty) {
      phase = BookPhase.idle;
      notifyListeners();
      return;
    }
    await submitUtterance(text, source: 'voice');
  }

  Future<void> confirmDone() async {
    await submitUtterance('好了', source: 'text');
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
