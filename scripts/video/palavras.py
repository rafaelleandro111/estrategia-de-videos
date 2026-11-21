"""Gera o tempo de cada palavra de uma narração (pra legenda).
Uso: python palavras.py narracao.wav saida.json [--idioma pt]
"""
import json
import shutil
import subprocess
import sys

import numpy as np
from faster_whisper import WhisperModel

FFMPEG_WINGET = r"C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"


def ffmpeg_bin():
    return shutil.which("ffmpeg") or FFMPEG_WINGET


def carregar(wav):
    # 16 kHz mono float32 via FFmpeg (o leitor PyAV quebra no Python 3.14)
    raw = subprocess.run(
        [ffmpeg_bin(), "-v", "error", "-i", wav, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def transcrever(wav, idioma="pt", modelo="small"):
    m = WhisperModel(modelo, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(carregar(wav), language=idioma, word_timestamps=True)
    out = []
    for s in segs:
        for w in s.words:
            out.append({"text": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)})
    return out


if __name__ == "__main__":
    wav, saida = sys.argv[1], sys.argv[2]
    idioma = sys.argv[sys.argv.index("--idioma") + 1] if "--idioma" in sys.argv else "pt"
    palavras = transcrever(wav, idioma)
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(palavras, f, ensure_ascii=False, indent=1)
    print(f"{len(palavras)} palavras -> {saida}")
