#!/usr/bin/env bash
# 下载端侧 SenseVoice 模型到 mobile/assets/asr/。onnx 不进 git。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/mobile/assets/asr"
mkdir -p "$DEST"
if [[ -f "$DEST/model.int8.onnx" ]]; then
  SIZE="$(stat -f%z "$DEST/model.int8.onnx" 2>/dev/null || stat -c%s "$DEST/model.int8.onnx")"
  if [[ "$SIZE" -gt 1000000 ]]; then
    echo "already have $DEST/model.int8.onnx"
    exit 0
  fi
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2"
curl -fL --retry 3 -o "$TMP/sv.tar.bz2" "$URL"
tar -xjf "$TMP/sv.tar.bz2" -C "$TMP"
cp "$TMP"/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/model.int8.onnx "$DEST/"
cp "$TMP"/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/tokens.txt "$DEST/"
ls -lh "$DEST"
