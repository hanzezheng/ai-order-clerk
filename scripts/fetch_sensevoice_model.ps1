# 下载端侧 SenseVoice 模型到 mobile/assets/asr/。onnx 不进 git。
# Windows 自带 tar 解 bz2 会卡住，用 Python tarfile。
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Dest = Join-Path $Root "mobile\assets\asr"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$Onnx = Join-Path $Dest "model.int8.onnx"
if ((Test-Path $Onnx) -and (Get-Item $Onnx).Length -gt 1MB) {
  Write-Host "already have $Onnx"
  exit 0
}
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }
$Tmp = Join-Path $env:TEMP "sensevoice-fetch"
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
$Archive = Join-Path $Tmp "sv.tar.bz2"
$Url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2"
if (-not (Test-Path $Archive) -or (Get-Item $Archive).Length -lt 1MB) {
  curl.exe --noproxy "*" -fL --retry 3 --retry-all-errors -o $Archive $Url
  if ($LASTEXITCODE -ne 0) { throw "curl failed: $LASTEXITCODE" }
}
& $Py -c @"
from pathlib import Path
import tarfile
archive = Path(r'$Archive')
dest = Path(r'$Dest')
wanted = {'model.int8.onnx', 'tokens.txt'}
with tarfile.open(archive, 'r:bz2') as tf:
    for member in tf:
        name = Path(member.name).name
        if name not in wanted or not member.isfile():
            continue
        src = tf.extractfile(member)
        if src is None:
            continue
        (dest / name).write_bytes(src.read())
print('ok')
"@
Get-ChildItem $Dest | Format-Table Name, Length
