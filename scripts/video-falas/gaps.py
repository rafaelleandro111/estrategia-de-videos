# Mostra palavras e pausas perto de tempos dados
import json, sys
ws = [w for s in json.load(open(sys.argv[1], encoding="utf-8")) for w in s["words"]]
for t in map(float, sys.argv[2:]):
    print(f"--- {t}")
    for p, w in zip(ws, ws[1:]):
        if t - 3 < w[0] < t + 3:
            print(f"  {w[0]:7.2f}-{w[1]:7.2f} (pausa {w[0]-p[1]:4.2f}) {w[2]}")
