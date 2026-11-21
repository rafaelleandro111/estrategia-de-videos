# Uso: python -I bordas.py <pasta-do-video> <pasta-transcricoes>
# Mostra, pra cada trecho, as palavras de borda (as que entram e as vizinhas que ficam de fora)
import json, sys, os
pasta, trans = sys.argv[1], sys.argv[2]
for tr in json.load(open(os.path.join(pasta, "trechos.json"), encoding="utf-8")):
    ws = [w for s in json.load(open(os.path.join(trans, tr["fonte"] + ".json"), encoding="utf-8")) for w in s["words"]]
    idx = [k for k, w in enumerate(ws) if w[0] >= tr["ini"] - 0.05 and w[1] <= tr["fim"] + 0.05]
    a, b = idx[0], idx[-1]
    fora_a = " ".join(w[2] for w in ws[max(0, a - 4):a])
    fora_b = " ".join(w[2] for w in ws[b + 1:b + 5])
    dentro_a = " ".join(w[2] for w in ws[a:a + 5])
    dentro_b = " ".join(w[2] for w in ws[b - 4:b + 1])
    print(f"{tr['n']:2d} [{fora_a}] >> {dentro_a} ... {dentro_b} << [{fora_b}]")
