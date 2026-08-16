(function (root) {
  const CLOSING_WORDS = ["好了", "就这样", "可以了", "定了"];

  function trimTranscript(text) {
    return String(text || "").trim();
  }

  function hasSpeechContent(text) {
    const stripped = trimTranscript(text);
    if (!stripped) return false;
    for (const char of stripped) {
      if (/[0-9A-Za-z\u4e00-\u9fff]/.test(char)) return true;
    }
    return false;
  }

  function expectMoreFor(text) {
    const stripped = trimTranscript(text);
    if (CLOSING_WORDS.indexOf(stripped) !== -1) return false;
    return !CLOSING_WORDS.some((word) => stripped.indexOf(word) !== -1);
  }

  function createVoiceController(opts) {
    const transport = opts.transport;
    const tts = opts.tts || { speak: function () {}, interrupt: function () {} };
    const onChange = opts.onChange || function () {};
    const state = {
      phase: "IDLE",
      sessionId: null,
      seq: 0,
      utteranceId: null,
      overlay: "",
      replyText: "",
      hint: "",
      last: null,
      hold: false,
      source: "voice",
      playId: null,
    };

    function emit() {
      onChange(state);
    }

    async function startNewSession() {
      const body = await transport.createSession();
      state.sessionId = body.session_id;
      state.seq = 0;
      state.utteranceId = null;
      state.overlay = "";
      state.hold = false;
      state.last = body;
      state.phase = "IDLE";
      state.hint = "";
      emit();
      return body;
    }

    async function ensureSession() {
      if (!state.sessionId) return startNewSession();
      return state.last;
    }

    function newId() {
      return (opts.uuid || (function () { return crypto.randomUUID(); }))();
    }

    function press() {
      if (state.phase === "PROCESSING") return { posted: false, reason: "busy" };
      if (state.phase === "DONE") {
        return { posted: false, reason: "new_session", startNew: true };
      }
      if (state.phase === "SPEAKING") tts.interrupt();
      if (state.phase === "LISTENING") return { posted: false, reason: "already_listening" };
      state.utteranceId = newId();
      state.overlay = "";
      state.hold = true;
      state.hint = "";
      state.phase = "LISTENING";
      emit();
      return { posted: false, reason: "listening" };
    }

    function notePartial(text) {
      if (state.phase !== "LISTENING") return;
      state.overlay = text;
      emit();
    }

    async function postFinal(text, utteranceId) {
      await ensureSession();
      const said = trimTranscript(text);
      if (!hasSpeechContent(said)) {
        state.phase = "IDLE";
        state.utteranceId = null;
        emit();
        return { posted: false, reason: "empty" };
      }
      state.phase = "PROCESSING";
      state.seq += 1;
      const command = {
        text: said,
        source: "voice",
        utterance_id: utteranceId,
        seq: state.seq,
        is_final: true,
        expect_more: expectMoreFor(said)
      };
      state.utteranceId = null;
      emit();
      const result = await transport.postTurn(state.sessionId, command);
      if (result.status === 409 && result.body && result.body.detail === "task_completed") {
        await startNewSession();
        return { posted: false, reason: "task_completed" };
      }
      if (result.status !== 200) {
        state.seq -= 1;
        state.phase = "IDLE";
        state.hint = "这句没接上，请再说一遍。";
        emit();
        return { posted: true, reason: "http_error", status: result.status, body: result.body };
      }
      const body = result.body;
      state.last = body;
      state.replyText = body.reply_text || "";
      state.hint = "";
      const confirmed = body.draft && body.draft.status === "confirmed";
      if (body.ignored || !state.replyText) {
        state.phase = confirmed ? "DONE" : "IDLE";
        emit();
        return { posted: true, reason: "accepted_silent", body: body };
      }
      state.playId = newId();
      state.phase = confirmed ? "DONE" : "SPEAKING";
      emit();
      tts.speak(state.replyText, state.playId);
      return { posted: true, reason: "accepted", body: body };
    }

    async function releaseFinal(text) {
      if (state.phase !== "LISTENING" || !state.hold) {
        return { posted: false, reason: "not_listening" };
      }
      state.hold = false;
      const utteranceId = state.utteranceId || newId();
      state.overlay = "";
      if (!hasSpeechContent(text)) {
        state.utteranceId = null;
        state.phase = "IDLE";
        emit();
        return { posted: false, reason: "empty" };
      }
      return postFinal(text, utteranceId);
    }

    async function submitFakeFinal(text) {
      if (state.phase === "PROCESSING") return { posted: false, reason: "busy" };
      if (state.phase === "DONE") {
        await startNewSession();
        return { posted: false, reason: "new_session" };
      }
      if (state.phase === "SPEAKING") tts.interrupt();
      if (state.phase === "LISTENING") state.hold = false;
      return postFinal(text, newId());
    }

    async function confirmDone() {
      if (state.phase === "PROCESSING" || state.phase === "DONE") {
        return { posted: false, reason: "busy" };
      }
      if (state.phase === "LISTENING") return releaseFinal("");
      if (state.phase === "SPEAKING") tts.interrupt();
      return submitFakeFinal("好了");
    }

    function onTtsEnded(playId) {
      if (playId && playId !== state.playId) return;
      if (state.phase === "SPEAKING") {
        state.phase = "IDLE";
        emit();
      }
    }

    function onTtsInterrupted() {
      if (state.phase === "SPEAKING") {
        state.phase = state.hold ? "LISTENING" : "IDLE";
        emit();
      }
    }

    return {
      state: state,
      CLOSING_WORDS: CLOSING_WORDS,
      expectMoreFor: expectMoreFor,
      press: press,
      notePartial: notePartial,
      releaseFinal: releaseFinal,
      submitFakeFinal: submitFakeFinal,
      confirmDone: confirmDone,
      startNewSession: startNewSession,
      onTtsEnded: onTtsEnded,
      onTtsInterrupted: onTtsInterrupted
    };
  }

  function createBrowserTts(onEnded, onInterrupted) {
    return {
      speak: function (text, playId) {
        if (!root.speechSynthesis || typeof root.SpeechSynthesisUtterance !== "function") {
          onEnded(playId);
          return;
        }
        root.speechSynthesis.cancel();
        const utterance = new root.SpeechSynthesisUtterance(text);
        utterance.onend = function () { onEnded(playId); };
        utterance.onerror = function () { onEnded(playId); };
        root.speechSynthesis.speak(utterance);
      },
      interrupt: function () {
        if (root.speechSynthesis) root.speechSynthesis.cancel();
        onInterrupted();
      }
    };
  }

  function createBrowserAsr(onPartial, onFinal) {
    const Rec = root.SpeechRecognition || root.webkitSpeechRecognition;
    if (!Rec) return null;
    const rec = new Rec();
    rec.lang = "zh-CN";
    rec.continuous = false;
    rec.interimResults = true;
    rec.onresult = function (event) {
      let finalText = "";
      let partial = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const chunk = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += chunk;
        else partial += chunk;
      }
      if (partial) onPartial(partial);
      if (finalText) onFinal(finalText);
    };
    return rec;
  }

  root.VoiceShell = {
    CLOSING_WORDS: CLOSING_WORDS,
    expectMoreFor: expectMoreFor,
    createVoiceController: createVoiceController,
    createBrowserTts: createBrowserTts,
    createBrowserAsr: createBrowserAsr
  };
})(window);
