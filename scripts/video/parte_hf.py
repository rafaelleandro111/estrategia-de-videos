"""Monta UMA parte (~3 min) de um edit de personagem no HyperFrames, leve o bastante pro Studio.

Uso (na raiz do projeto):
    python scripts/video/parte_hf.py marketing/youtube/<pasta-do-video>/<parte>            # corta trechos + monta
    python scripts/video/parte_hf.py marketing/youtube/<pasta-do-video>/<parte> --conferir # checa o MP4 renderizado

<parte>/parte.json:
  {"musica": {"arquivo": "../musica/x.mp3", "inicio": 0}, "transicao": 0.3,
   "segmentos": [
     {"tipo": "fala", "src": "<id em ../fontes>", "ini": s, "fim": s, "legenda": [[ini, fim, "texto"], ...]},
     {"tipo": "mudo", "src": "<id>", "ini": s, "dur": s}
   ]}
Opcional: "emenda_inicio"/"emenda_fim": true quando a parte vizinha toca a mesma música (sem escurecer nem fade).
Regras (ver _memoria/preferencias.md): fala entra inteira (o trecho escolhido já começa e termina no silêncio),
tela cheia 16:9 sem marca d'água (../fontes/areas.json), música abaixa nas falas, só os trechos usados viram arquivo.
"""
import html
import json
import subprocess
import sys
from pathlib import Path

BAIXA_PRIORIDADE = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS: não trava o PC
W, H = 1920, 1080
FILTRO = ("{crop},scale=1920:1080:flags=lanczos,setsar=1,hqdn3d=1.2:1.2:4:4,cas=0.5,"
          "eq=contrast=1.08:saturation=1.10:brightness=0.01,colorbalance=rs=-0.02:bs=0.03:rh=0.04:bh=-0.03")
MUS_ALTA, MUS_BAIXA = 0.6, 0.17  # música sempre abaixo da voz (pedido do dono)
VOZ_ALVO = -26.0  # LUFS que cada fala soa no vídeo; o ganho de cada cena sai da medição (todas no mesmo nível)
FADE_FINAL = 2.5


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], creationflags=BAIXA_PRIORIDADE, check=True, **kw)


def crop_169(x, y, w, h):
    if w / h > W / H:
        nw = round(h * W / H / 2) * 2
        return f"crop={nw}:{h}:{x + (w - nw) // 2}:{y}"
    nh = round(w * H / W / 2) * 2
    return f"crop={w}:{nh}:{x}:{y + (h - nh) // 2}"


def duracao(arq):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def auto(points):
    pts = sorted({round(t, 3): round(v, 3) for t, v in points}.items())
    return html.escape(json.dumps({"version": 1, "lanes": [{"target": "volume",
                                   "points": [{"t": t, "v": v} for t, v in pts]}]}), quote=True)


def ganho_voz(arq):
    """Ganho pra fala soar em VOZ_ALVO. Usa o maior entre a média e o pico curto - 4 (cena com grito ou explosão abaixa mais)."""
    cache = arq.with_suffix(".lufs")
    if not cache.exists():
        log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(arq), "-vn", "-af",
                              "ebur128=metadata=1,ametadata=print:key=lavfi.r128.S", "-f", "null", "-"],
                             capture_output=True, text=True, creationflags=BAIXA_PRIORIDADE).stderr
        integ = float(log.rsplit("I:", 1)[1].split("LUFS")[0])
        curto = max(float(l.rsplit("=", 1)[1]) for l in log.splitlines() if "lavfi.r128.S=" in l)
        cache.write_text(f"{integ} {curto}")
    integ, curto = map(float, cache.read_text().split())
    return round(min(1.0, 10 ** ((VOZ_ALVO - max(integ, curto - 4)) / 20)), 3)


def nome(s):
    """Arquivo do trecho pelo conteúdo (mudar a ordem não obriga a cortar de novo)."""
    fim = s["fim"] if s["tipo"] == "fala" else s["ini"] + s["dur"]
    return f'{s["tipo"]}_{s["src"]}_{s["ini"]:.2f}_{fim:.2f}.mp4'.replace("-", "~")


def cortar(parte, fontes, areas, segs):
    media = parte / "media"
    media.mkdir(exist_ok=True)
    capas = [dict(s["capa"], tipo="mudo") for s in segs if s.get("capa")]
    for i, s in enumerate(segs + capas):
        fim = s["fim"] if s["tipo"] == "fala" else s["ini"] + s["dur"]
        saida = media / nome(s)
        if saida.exists():
            continue  # já cortado igual
        som = (["-af", "loudnorm=I=-20:TP=-2:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
               if s["tipo"] == "fala" else ["-an"])
        run(["ffmpeg", "-v", "error", "-y", "-ss", f'{s["ini"]:.3f}', "-to", f"{fim:.3f}", "-i", fontes / f'{s["src"]}.mp4',
             "-vf", FILTRO.format(crop=crop_169(*areas[s["src"]])), "-c:v", "libx264", "-preset", "medium",
             "-crf", "18", "-g", "30", "-keyint_min", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart", *som, saida])
        # -g 30: quadro-chave a cada 1 s; com menos, o render do HyperFrames congela a imagem
        print(f"  trecho {i + 1}/{len(segs) + len(capas)} ok", flush=True)


def montar(parte, cfg):
    segs, d = cfg["segmentos"], cfg.get("transicao", 0.3)
    media = parte / "media"
    t, clips, tweens, legs, falas = 0.0, [], [], [], []
    for i, s in enumerate(segs):
        arq = nome(s)
        dur = round(duracao(media / arq), 3)
        t0 = round(t, 3)
        if s["tipo"] == "fala":
            v = ganho_voz(media / arq)
            som = f'data-has-audio="true" data-automation="{auto([(0, 0), (0.05, v), (dur - 0.1, v), (dur, 0)])}"'
            falas.append((t0, t0 + dur))
            for a, b, txt in s.get("legenda", []):
                legs.append((round(t0 + a - s["ini"], 3), round(t0 + min(b, s["fim"]) - s["ini"], 3), txt))
        else:
            som = "muted"
        clips.append(f'      <div id="w{i:02d}" class="tomada" style="z-index:{i + 1}">\n'
                     f'        <video id="s{i:02d}" class="clip" src="media/{arq}" data-start="{t0}" '
                     f'data-duration="{dur}" data-track-index="{i % 2}" playsinline {som}></video>\n      </div>')
        if i:
            tweens.append(f'tl.fromTo("#w{i:02d}", {{ opacity: 0 }}, {{ opacity: 1, duration: {d}, ease: "none" }}, {t0});')
        if s.get("capa"):  # outra imagem por cima do começo da fala; a voz continua igual
            c = dict(s["capa"], tipo="mudo")
            clips.append(f'      <div id="c{i:02d}" class="tomada" style="z-index:{500 + i}">\n'
                         f'        <video id="capa{i:02d}" class="clip" src="media/{nome(c)}" data-start="{t0}" '
                         f'data-duration="{c["dur"]}" data-track-index="2" playsinline muted></video>\n      </div>')
            tweens.append(f'tl.fromTo("#c{i:02d}", {{ opacity: 1 }}, {{ opacity: 0, duration: {d}, ease: "none", '
                          f'immediateRender: false }}, {round(t0 + c["dur"] - d, 3)});')
        t += dur - d
    total = round(t + d, 3)

    # música: abaixa nas falas, sobe nas cenas sem fala
    m = cfg["musica"]
    mus = media / "musica.m4a"
    if not mus.exists():
        run(["ffmpeg", "-v", "error", "-y", "-i", (parte / m["arquivo"]).resolve(), "-af", "loudnorm=I=-22:TP=-2:LRA=11",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", mus])
    mdur = round(min(total, duracao(mus) - m.get("inicio", 0)), 3)
    if mdur < total - 0.5:
        print(f"  AVISO: a música acaba em {mdur:.1f}s e a parte tem {total:.1f}s")
    # "emenda_inicio"/"emenda_fim": a parte se junta à vizinha que toca a mesma música, sem escurecer nem abaixar
    ei, ef = cfg.get("emenda_inicio", False), cfg.get("emenda_fim", False)
    ini_m, fim_m = (0, 0.1) if ei else (1.5, 1.6), mdur if ef else mdur - FADE_FINAL
    pts = [(0, MUS_ALTA)] if ei else [(0, 0), (1.5, MUS_ALTA)]
    for a, b in falas:
        pts += [(max(a - 0.3, ini_m[0]), MUS_ALTA), (max(a + 0.2, ini_m[1]), MUS_BAIXA),
                (min(b - 0.4, fim_m), MUS_BAIXA), (min(b + 0.3, fim_m), MUS_ALTA)]
    pts += [(mdur, MUS_ALTA)] if ef else [(mdur - FADE_FINAL, MUS_ALTA), (mdur, 0)]
    musica = (f'      <audio id="musica" src="media/musica.m4a" data-start="0" data-duration="{mdur}" '
              f'data-media-start="{m.get("inicio", 0)}" data-track-index="3" data-automation="{auto(pts)}"></audio>')

    legs.sort()
    leg_html = []
    for k, (a, b, txt) in enumerate(legs):
        if k + 1 < len(legs):
            b = min(b, legs[k + 1][0] - 0.05)
        leg_html.append(f'      <div id="l{k:02d}" class="clip legenda" data-start="{a}" data-duration="{round(b - a, 3)}" '
                        f'data-track-index="4">{html.escape(txt)}</div>')

    fonte = media / "Legenda.ttf"
    if not fonte.exists():
        fonte.write_bytes(Path(r"C:\Windows\Fonts\seguisb.ttf").read_bytes())

    escuro_ini = ("" if ei else
                  'tl.fromTo("#escuro", { opacity: 1 }, { opacity: 0, duration: 1.0, ease: "none" }, 0);')
    escuro_fim = ("" if ef else f'tl.fromTo("#escuro", {{ opacity: 0 }}, {{ opacity: 1, duration: {FADE_FINAL}, '
                                f'ease: "none", immediateRender: false }}, {round(total - FADE_FINAL, 3)});')

    doc = f"""<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Legenda"; src: url("media/Legenda.ttf"); font-weight: 600; }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: 100%; height: 100%; background: #000; overflow: hidden; }}
      .tomada {{ position: absolute; inset: 0; }}
      .tomada video {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
      .legenda {{ position: absolute; left: 210px; right: 210px; bottom: 70px; z-index: 900; text-align: center;
                  font-family: "Legenda", sans-serif; font-weight: 600; font-size: 46px; line-height: 1.25; color: #fff;
                  text-shadow: 0 0 6px #000, 0 2px 3px #000, 0 0 2px #000; }}
      #escuro {{ position: absolute; inset: 0; z-index: 950; background: #000; }}
    </style>
  </head>
  <body>
    <!-- Gerado por scripts/video/parte_hf.py a partir de parte.json. -->
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1920" data-height="1080">
{chr(10).join(clips)}
{chr(10).join(leg_html)}
      <div id="escuro"{' style="opacity: 0"' if ei else ''}></div>
{musica}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      {escuro_ini}
      {(chr(10) + '      ').join(tweens)}
      {escuro_fim}
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
"""
    (parte / "index.html").write_text(doc, encoding="utf-8")
    print(f"{len(segs)} trechos, {len(falas)} falas, {len(legs)} legendas, duração {int(total // 60)}:{total % 60:04.1f}")


def main():
    parte = Path(sys.argv[1]).resolve()
    fontes = parte.parent / "fontes"
    cfg = json.loads((parte / "parte.json").read_text(encoding="utf-8"))
    areas = json.loads((fontes / "areas.json").read_text(encoding="utf-8"))
    cortar(parte, fontes, areas, cfg["segmentos"])
    montar(parte, cfg)


if __name__ == "__main__":
    main()
