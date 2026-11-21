# Uso: python -I transcrever.py <pasta-fontes> <pasta-saida> <janelas.json>
# Transcreve janelas de cada fonte com tempo por palavra (faster-whisper medium, CPU)
import json, sys, os
from faster_whisper import WhisperModel
import subprocess, numpy as np
def audio(f):
    raw=subprocess.run(["ffmpeg","-v","error","-i",f,"-ac","1","-ar","16000","-f","s16le","-"],capture_output=True,check=True).stdout
    return np.frombuffer(raw,np.int16).astype(np.float32)/32768.0
fontes = sys.argv[1]; saida = sys.argv[2]
janelas = json.load(open(sys.argv[3], encoding="utf-8"))  # {"id": [ini, fim, ini, fim...]} em segundos
m = WhisperModel("medium", device="cpu", compute_type="int8", cpu_threads=4)
for vid, clip in janelas.items():
    out = os.path.join(saida, vid + ".json")
    if os.path.exists(out): continue
    segs, _ = m.transcribe(audio(os.path.join(fontes, vid + ".mp4")), language="pt", beam_size=5,
                           word_timestamps=True, clip_timestamps=clip, vad_filter=False,
                           condition_on_previous_text=False)
    res = [{"start": s.start, "end": s.end, "text": s.text.strip(),
            "words": [[w.start, w.end, w.word.strip()] for w in s.words]} for s in segs]
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(vid, len(res), "segmentos", flush=True)
