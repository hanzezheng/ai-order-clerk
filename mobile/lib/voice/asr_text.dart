/// ASR 只交出 final 文本。禁止口令映射、禁止用 LLM 修识别结果。
String asrFinalText(String raw) {
  return raw.replaceAll(RegExp(r'<\|[^|]*\|>'), '').replaceAll(RegExp(r'\s+'), ' ').trim();
}
