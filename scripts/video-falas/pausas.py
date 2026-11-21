# Lista frases separadas por pausas >= 0.45s (bons pontos de corte), com tempo
import json, sys
ws = [w for s in json.load(open(sys.argv[1], encoding="utf-8")) for w in s["words"]]
a, frase = ws[0][0], [ws[0][2]]
for p, w in zip(ws, ws[1:]):
    gap = w[0] - p[1]
    if gap >= 0.45 or gap > 3:
        print(f"{a:7.2f}-{p[1]:7.2f} (pausa {gap:4.2f}) {' '.join(frase)}")
        a, frase = w[0], []
    frase.append(w[2])
print(f"{a:7.2f}-{ws[-1][1]:7.2f} {' '.join(frase)}")
