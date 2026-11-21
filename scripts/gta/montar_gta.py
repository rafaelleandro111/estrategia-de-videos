"""
Monta um episódio de corte de live de GTA (sem P&B, sem música, sem cards).

Uso:
  python -I scripts/gta/montar_gta.py <pasta-do-video> [teste]

Lê <pasta>/episodio.json:
{
  "fonte": "fontes/parte1.mp4",
  "transcricao": "transcricoes/parte1.json",   # faster-whisper com tempo por palavra
  "streamer": "@PaulinhoLOKOoficial",
  "cam": [36, 18, 352, 348],                    # caixa da webcam na fonte (x, y, w, h)
  "zoom_caixa": [444, 250, 0, 40],              # opcional: recorte do zoom (w, h, x, y), ex. só o rosto
  "borrar": [[1786, 294, 24, 24]],              # opcional: caixas (x, y, w, h) borradas (logo/nome da Kick)
  "trechos": [ {"ini": 95.0, "fim": 180.5, "zoom": [[120.0, 123.5]]}, ... ],   # tempos na fonte (s)
             # tela de aviso: {"ini": 446, "fim": 449, "card": ["LINHA 1", "LINHA 2"]} (fundo borrado, sem legenda)
  "corrigir": {"palavra errada": "palavra certa"}
}
Compilação (vários streamers): cada trecho pode trazer a própria "fonte", "cam", "zoom_caixa",
"borrar" e "streamer". A transcrição dessa fonte fica em transcricoes/<nome-da-fonte>.json.
  "censura": [[x, y, w, h, ini, fim], ...]  borrão forte numa área só nesse tempo (na fonte)

Faz:
  1. build/segNN.mp4: um trecho por vez (-ss antes do -i, lição 38), com zoom na webcam nos tempos marcados
  2. legenda.ass: legenda palavra por palavra (palavra falada em amarelo) + @ do streamer fixo
  3. final.mp4: junta os trechos, queima a legenda e nivela o som (loudnorm)
  4. provas/: quadros antes x depois + lista dos trechos usados (pra recurso de monetização)
"""
import json
import subprocess
import sys
from pathlib import Path

BAIXA = 0x4000  # BELOW_NORMAL_PRIORITY_CLASS (lição 2)
FONTS = "C\\:/Windows/Fonts"


def rodar(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=BAIXA)
    if r.returncode != 0:
        sys.exit(f"ERRO ffmpeg ({r.returncode}): {r.stderr[-800:]}")


def caixa_zoom(cam, altura_min=400):
    """Recorte 16:9 que contém a webcam inteira, colado no canto dela."""
    x, y, w, h = cam
    alt = max(altura_min, h + 40)
    larg = int(alt * 16 / 9) // 2 * 2
    alt = alt // 2 * 2
    cx, cy = x + w // 2, y + h // 2
    x0 = min(max(0, cx - larg // 2), 1920 - larg)
    y0 = min(max(0, cy - alt // 2), 1080 - alt)
    return larg, alt, x0, y0


def montar_seg(fonte, t, n, cam, build, caixa=None, fade_in=True, fade_out=True, borrar=None):
    fonte, cam = t.get("_fonte", fonte), t.get("cam", cam)
    caixa, borrar = t.get("zoom_caixa", caixa), t.get("borrar", borrar)
    out = build / f"seg{n:02d}.mp4"
    if out.exists():
        return out
    dur = t["fim"] - t["ini"]
    zooms = [(max(0, a - t["ini"]), min(dur, b - t["ini"])) for a, b in t.get("zoom", [])
             if b > t["ini"] and a < t["fim"]]
    # borrar: [[x, y, w, h], ...] na fonte (logo/nome da Kick). Antes do zoom, pra sumir também ampliado
    src = "[0:v]" + (",".join(f"delogo=x={x}:y={y}:w={w}:h={h}" for x, y, w, h in borrar) + "[src];[src]"
                     if borrar else "")
    for k, (x, y, w, h, a, b) in enumerate(t.get("censura", [])):
        a, b = max(0, a - t["ini"]), min(dur, b - t["ini"])
        src += (f"split[c{k}a][c{k}b];[c{k}b]crop={w}:{h}:{x}:{y},boxblur=40:6[c{k}c];"
                f"[c{k}a][c{k}c]overlay={x}:{y}:enable='between(t,{a:.3f},{b:.3f})'[c{k}d];[c{k}d]")
    if t.get("card"):
        # tela de aviso: o trecho da fonte borrado e escuro, com 1 ou 2 linhas de texto no meio
        linhas = t["card"]
        txt = "".join(
            f",drawtext=fontfile='C\\:/Windows/Fonts/ariblk.ttf':text='{l}':fontsize=92:"
            f"fontcolor={'white' if i == 0 else '0xFFE500'}:borderw=5:bordercolor=black:"
            f"x=(w-text_w)/2:y=(h/2)-{120 if len(linhas) > 1 else 50}+{i * 150}"
            for i, l in enumerate(linhas))
        vf = f"{src}boxblur=24:3,eq=brightness=-0.28{txt},fps=60,format=yuv420p[v]"
    elif zooms:
        lz, az, xz, yz = caixa or caixa_zoom(cam)
        quando = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in zooms)
        vf = (f"{src}split[a][b];[b]crop={lz}:{az}:{xz}:{yz},scale=1920:1080:flags=lanczos[z];"
              f"[a][z]overlay=0:0:enable='{quando}',fps=60,format=yuv420p[v]")
    else:
        vf = f"{src}fps=60,format=yuv420p[v]"
    # trechos colados (fim de um = início do outro) não levam fade na emenda: som contínuo
    fades = (["afade=t=in:d=0.08"] if fade_in else []) + \
            ([f"afade=t=out:st={max(0, dur - 0.12):.3f}:d=0.12"] if fade_out else [])
    if t.get("card"):
        fades = ["volume=0.35"] + fades  # som do jogo baixinho por trás da tela
    af = "[0:a]" + (",".join(fades) or "anull") + "[a]"
    tmp = out.with_suffix(".tmp.mp4")
    rodar(["ffmpeg", "-v", "error", "-y", "-ss", f"{t['ini']:.3f}", "-t", f"{dur:.3f}", "-i", str(fonte),
           "-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "aac", "-b:a", "192k",
           "-ar", "48000", str(tmp)])
    tmp.replace(out)
    return out


def ts(s):
    h, r = divmod(max(0, s), 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def limpar(p, corrigir):
    p = p.strip()
    for errado, certo in corrigir.items():
        if p.lower().strip(".,!?") == errado.lower():
            p = certo
    return p.upper()


def gerar_ass(ep, palavras, trechos, saida):
    corrigir = ep.get("corrigir", {})
    so = ep.get("legenda_so")  # [[ini, fim], ...] na fonte: só legendar aí (fala do streamer, não do jogo)
    if so:
        palavras = [p for p in palavras if any(a <= p[0] <= b for a, b in so)]
    linhas = []
    desloc = 0.0
    for t in trechos:
        ws = [] if t.get("card") else [
            (a - t["ini"] + desloc, b - t["ini"] + desloc, limpar(w, corrigir))
            for a, b, w in t.get("_palavras", palavras) if a >= t["ini"] - 0.05 and b <= t["fim"] + 0.05 and w.strip()]
        # blocos de até 3 palavras; quebra em pausa > 0,6 s
        blocos, atual = [], []
        for w in ws:
            if atual and (len(atual) == 3 or w[0] - atual[-1][1] > 0.6):
                blocos.append(atual)
                atual = []
            atual.append(w)
        if atual:
            blocos.append(atual)
        fim_trecho = t["fim"] - t["ini"] + desloc
        for i, bl in enumerate(blocos):
            prox = blocos[i + 1][0][0] if i + 1 < len(blocos) else fim_trecho
            for j, (a, b, _) in enumerate(bl):
                ini = a
                fim = bl[j + 1][0] if j + 1 < len(bl) else min(prox, max(b, a + 0.25) + 0.35)
                fim = min(fim, fim_trecho)
                if fim <= ini:
                    continue
                txt = " ".join(("{\\c&H00E5FF&}" + w + "{\\c&HFFFFFF&}") if k == j else w
                               for k, (_, _, w) in enumerate(bl)).replace(" -", "-")
                linhas.append(f"Dialogue: 0,{ts(ini)},{ts(fim)},Leg,,0,0,0,,{txt}")
        if t.get("streamer"):
            linhas.append(f"Dialogue: 1,{ts(desloc)},{ts(fim_trecho)},Tag,,0,0,0,,{t['streamer']}")
        desloc += t["fim"] - t["ini"]
    total = desloc
    if ep.get("streamer"):
        linhas.append(f"Dialogue: 1,{ts(0)},{ts(total)},Tag,,0,0,0,,{ep['streamer']}")
    if ep.get("marca"):  # marca d'água do canal, canto de baixo à direita
        linhas.append(f"Dialogue: 1,{ts(0)},{ts(total)},Marca,,0,0,0,,{ep['marca']}")
    cab = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Leg,Arial Black,50,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,4,2,2,80,80,150,1
Style: Tag,Arial Black,34,&H33FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,0,9,40,40,36,1
Style: Marca,Arial Black,34,&H33FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,0,3,40,40,36,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    saida.write_text(cab + "\n".join(linhas) + "\n", encoding="utf-8")
    return total


def provas(pasta, fonte, trechos, final):
    pv = pasta / "provas"
    pv.mkdir(exist_ok=True)
    desloc = 0.0
    lista = ["Trechos usados (tempo na live original -> tempo no vídeo final)"]
    for n, t in enumerate(trechos):
        d = t["fim"] - t["ini"]
        lista.append(f"{n + 1:02d}. {t.get('fonte', 'live')} {ts(t['ini'])} - {ts(t['fim'])}  ->  vídeo {ts(desloc)} - {ts(desloc + d)}"
                     + (f"  | zoom na reação: {len(t.get('zoom', []))}x" if t.get("zoom") else ""))
        if n % max(1, len(trechos) // 4) == 0:  # ~4 comparações antes x depois
            meio = t["zoom"][0][0] + 0.8 if t.get("zoom") else t["ini"] + d / 2
            rodar(["ffmpeg", "-v", "error", "-y", "-ss", f"{meio:.2f}", "-i", str(t.get("_fonte", fonte)),
                   "-ss", f"{desloc + meio - t['ini']:.2f}", "-i", str(final),
                   "-filter_complex", "[0:v]scale=960:540[a];[1:v]scale=960:540[b];[a][b]hstack",
                   "-frames:v", "1", str(pv / f"antes_depois_{n + 1:02d}.jpg")])
        desloc += d
    lista.append(f"\nDuração final: {ts(desloc)}  | live original usada: {ts(trechos[-1]['fim'] - trechos[0]['ini'])}")
    (pv / "trechos_usados.txt").write_text("\n".join(lista), encoding="utf-8")


def main():
    pasta = Path(sys.argv[1]).resolve()
    teste = len(sys.argv) > 2 and sys.argv[2] == "teste"
    ep = json.loads((pasta / "episodio.json").read_text(encoding="utf-8"))
    fonte = pasta / ep["fonte"] if ep.get("fonte") else None
    build = pasta / "build"
    build.mkdir(exist_ok=True)
    trechos = ep["trechos"][:1] if teste else ep["trechos"]
    cache = {}
    for t in trechos:
        if t.get("fonte"):
            f = pasta / t["fonte"]
            t["_fonte"] = f
            if f.stem not in cache:
                tr = pasta / "transcricoes" / f"{f.stem}.json"
                cache[f.stem] = [w for s in json.loads(tr.read_text(encoding="utf-8")) for w in s["words"]]                     if tr.exists() else []
            t["_palavras"] = cache[f.stem]

    segs = []
    for n, t in enumerate(trechos):
        mesma = lambda u: u.get("fonte") == t.get("fonte")
        colado_antes = n > 0 and mesma(trechos[n - 1]) and abs(trechos[n - 1]["fim"] - t["ini"]) < 0.01
        colado_depois = n + 1 < len(trechos) and mesma(trechos[n + 1]) and abs(trechos[n + 1]["ini"] - t["fim"]) < 0.01
        segs.append(montar_seg(fonte, t, n, ep.get("cam"), build, ep.get("zoom_caixa"),
                               fade_in=not colado_antes, fade_out=not colado_depois,
                               borrar=ep.get("borrar")))
        print(f"trecho {n + 1}/{len(trechos)} ok", flush=True)

    palavras = []
    if ep.get("transcricao"):
        trans = json.loads((pasta / ep["transcricao"]).read_text(encoding="utf-8"))
        palavras = [w for s in trans for w in s["words"]]
    ass = build / "legenda.ass"
    total = gerar_ass(ep, palavras, trechos, ass)

    lista = build / "lista.txt"
    lista.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    final = pasta / ("teste.mp4" if teste else "final.mp4")
    tmp = final.with_suffix(".tmp.mp4")
    ass_ff = ass.as_posix().replace(":", "\\:")
    rodar(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
           "-vf", f"subtitles='{ass_ff}':fontsdir='{FONTS}'",
           "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", str(tmp)])
    tmp.replace(final)
    print(f"pronto: {final} ({ts(total)})", flush=True)
    if not teste:
        provas(pasta, fonte, trechos, final)
        print("provas em", pasta / "provas", flush=True)


if __name__ == "__main__":
    main()
