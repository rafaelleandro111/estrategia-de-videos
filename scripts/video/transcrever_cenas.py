"""Transcreve todos os .mp4 de uma pasta (segmentos + palavras) pra achar as falas e montar a legenda.
Uso: python scripts/video/transcrever_cenas.py <pasta-fontes> [--modelo medium]
Salva <id>.json ao lado de cada vídeo (pula os que já existem).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from faster_whisper import WhisperModel  # noqa: E402
from palavras import carregar  # noqa: E402

pasta = Path(sys.argv[1])
modelo = sys.argv[sys.argv.index("--modelo") + 1] if "--modelo" in sys.argv else "medium"
m = WhisperModel(modelo, device="cpu", compute_type="int8", cpu_threads=12)
for mp4 in sorted(pasta.glob("*.mp4")):
    saida = mp4.with_suffix(".json")
    if saida.exists():
        continue
    segs, _ = m.transcribe(carregar(str(mp4)), language="pt", word_timestamps=True, vad_filter=True)
    out = []
    for s in segs:
        out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                    "words": [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for w in s.words]})
    saida.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    print(mp4.name, len(out), "falas", flush=True)
