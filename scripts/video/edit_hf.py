"""Monta o edit de personagem como composição HyperFrames (estilo VN_BR) a partir de <pasta>/roteiro.json.

Uso:
    python scripts/video/edit_hf.py marketing/youtube/<pasta-do-video>
    depois, em <pasta>/hf: npx --yes hyperframes@<versão> preview   (Studio)  |  ... render  (MP4)

Pré-requisito: scripts/video/preparar_fontes.py já gerou <pasta>/hf/media/<id>.mp4 (imagem tratada, 16:9 cheio)
e <id>.m4a (som com volume igualado).

roteiro.json:
  {"transicao": 0.3, "musicas": {"<ato>": {"arquivo": "x.mp3", "inicio": s}, ...}, "blocos": [...]}
  bloco fala:     {"tipo": "fala", "ato", "src", "ini", "fim", "legenda": [[ini, fim, "texto"], ...], "pausas": false}
                  sem "pausas", os silêncios longos entre as falas são cortados (ritmo mais rápido)
  bloco montagem: {"tipo": "montagem", "ato", "tomadas": [[src, ini, duração], ...]}  (sem som da cena, música sobe)
Cada ato usa a sua música; na troca de ato as músicas se cruzam. A música abaixa nas falas.
"""
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

D_MUS = 3.0          # crossfade entre as músicas na troca de ato
MUS_ALTA, MUS_BAIXA = 0.9, 0.35
VOZ = 0.8
JUNTA_FALAS = 2.0    # falas separadas por menos que isso ficam no mesmo trecho
FOLGA_ANTES, FOLGA_DEPOIS = 0.6, 0.9  # folga larga: o tempo do Whisper não é exato e cortava o começo/fim das palavras
FADE_FINAL = 2.5


def trechos(b):
    """Divide um bloco de fala em trechos [ini, fim] (tempo da fonte), cortando os silêncios longos."""
    if b.get("pausas") or not b["legenda"]:
        return [[b["ini"], b["fim"]]]
    out = []
    for s, e, _ in sorted(b["legenda"]):
        if out and s - out[-1][1] <= JUNTA_FALAS + FOLGA_DEPOIS:
            out[-1][1] = max(out[-1][1], e + FOLGA_DEPOIS)
        else:
            out.append([s - FOLGA_ANTES, e + FOLGA_DEPOIS])
    return [[max(b["ini"], s), min(b["fim"], e)] for s, e in out]


def auto(points):
    pts = sorted({round(t, 3): round(v, 3) for t, v in points}.items())
    return html.escape(json.dumps({"version": 1, "lanes": [{"target": "volume",
                                   "points": [{"t": t, "v": v} for t, v in pts]}]}), quote=True)


def duracao(arq):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def main():
    pasta = Path(sys.argv[1]).resolve()
    hf = pasta / "hf"
    media = hf / "media"
    cfg = json.loads((pasta / "roteiro.json").read_text(encoding="utf-8"))
    d = cfg.get("transicao", 0.3)

    # ------------------------------------------------------------ linha do tempo
    tomadas, falas_t, legendas, atos = [], [], [], {}
    t = 0.0
    for b in cfg["blocos"]:
        atos.setdefault(b["ato"], t)
        if b["tipo"] == "montagem":
            pecas = [(src, ini, ini + dur, False) for src, ini, dur in b["tomadas"]]
        else:
            pecas = [(b["src"], s, e, True) for s, e in trechos(b)]
        for src, ini, fim, som in pecas:
            dur = round(fim - ini, 3)
            tomadas.append({"src": src, "ini": ini, "dur": dur, "t": round(t, 3), "som": som})
            if som:
                falas_t.append((t, t + dur))
                for s, e, txt in b["legenda"]:
                    if s < fim and e > ini:  # legenda que cai neste trecho
                        legendas.append((round(t + max(s, ini) - ini, 3), round(t + min(e, fim) - ini, 3), txt))
            t += dur - d
    total = round(t + d, 3)

    # ------------------------------------------------------------ imagem (dissolve curto entre as tomadas)
    videos, tweens = [], []
    for i, c in enumerate(tomadas):
        videos.append(
            f'      <div id="w{i:03d}" class="tomada" style="z-index:{i + 1}">\n'
            f'        <video id="v{i:03d}" class="clip" src="media/{c["src"]}.mp4" data-start="{c["t"]}" '
            f'data-duration="{c["dur"]}" data-media-start="{c["ini"]}" data-track-index="{i % 2}" muted playsinline></video>\n'
            f"      </div>")
        if i:
            tweens.append(f'tl.fromTo("#w{i:03d}", {{ opacity: 0 }}, {{ opacity: 1, duration: {d}, ease: "none" }}, {c["t"]});')

    # ------------------------------------------------------------ fala (som separado da imagem)
    audios = []
    for j, c in enumerate(x for x in tomadas if x["som"]):
        dur = c["dur"]
        audios.append(
            f'      <audio id="f{j:03d}" src="media/{c["src"]}.m4a" data-start="{c["t"]}" data-duration="{dur}" '
            f'data-media-start="{c["ini"]}" data-track-index="{2 + j % 2}" '
            f'data-automation="{auto([(0, 0), (0.05, VOZ), (dur - 0.12, VOZ), (dur, 0)])}"></audio>')

    # ------------------------------------------------------------ música: uma por ato, abaixa nas falas
    juntas = []
    for a, b in sorted(falas_t):
        if juntas and a - juntas[-1][1] < 1.2:
            juntas[-1][1] = max(juntas[-1][1], b)
        else:
            juntas.append([a, b])
    ordem = sorted(atos.items(), key=lambda kv: kv[1])
    musicas = []
    for k, (ato, ini_ato) in enumerate(ordem):
        m = cfg["musicas"][ato]
        de = max(0.0, ini_ato - (D_MUS if k else 0))
        ate = ordem[k + 1][1] + D_MUS if k + 1 < len(ordem) else total
        src = media / f"musica-{Path(m['arquivo']).stem}.m4a"
        if not src.exists():  # volume igualado entre as faixas
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", pasta / "musica" / m["arquivo"], "-af",
                            "loudnorm=I=-18:TP=-2:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", src], check=True)
        dur = round(min(ate - de, duracao(src) - m["inicio"]), 3)
        ent = D_MUS if k else 1.5
        sai = D_MUS if k + 1 < len(ordem) else FADE_FINAL + 1
        pts = [(0, 0), (ent, MUS_ALTA)]
        for a, b in juntas:
            a, b = a - de, b - de
            if b <= ent or a >= dur - sai:
                continue
            pts += [(max(a - 0.3, ent), MUS_ALTA), (max(a, ent + 0.01), MUS_BAIXA),
                    (min(b, dur - sai - 0.01), MUS_BAIXA), (min(b + 0.6, dur - sai), MUS_ALTA)]
        pts += [(dur - sai, MUS_ALTA), (dur, 0)]
        musicas.append(
            f'      <audio id="musica-{ato}" src="media/{src.name}" data-start="{de:.3f}" data-duration="{dur}" '
            f'data-media-start="{m["inicio"]}" data-track-index="{4 + k % 2}" data-automation="{auto(pts)}"></audio>')

    # ------------------------------------------------------------ legenda
    legs = []
    for k, (a, b, txt) in enumerate(sorted(legendas)):
        if k + 1 < len(legendas):
            b = min(b, sorted(legendas)[k + 1][0] - 0.05)
        if b - a < 0.3:
            continue
        legs.append(f'      <div id="l{k:03d}" class="clip legenda" data-start="{a}" data-duration="{round(b - a, 3)}" '
                    f'data-track-index="6">{html.escape(txt)}</div>')

    # fonte da legenda (arquivo local, exigido pelo lint)
    (media / "fonts").mkdir(exist_ok=True)
    fonte = media / "fonts" / "seguisb.ttf"
    if not fonte.exists():
        shutil.copy(r"C:\Windows\Fonts\seguisb.ttf", fonte)

    doc = f"""<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Legenda"; src: url("media/fonts/seguisb.ttf"); font-weight: 600; }}
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
    <!-- Gerado por scripts/video/edit_hf.py a partir de roteiro.json. Edite o roteiro e rode o script de novo. -->
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1920" data-height="1080">
{chr(10).join(videos)}
{chr(10).join(legs)}
      <div id="escuro"></div>
{chr(10).join(audios)}
{chr(10).join(musicas)}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      tl.fromTo("#escuro", {{ opacity: 1 }}, {{ opacity: 0, duration: 1.2, ease: "none" }}, 0);
      {chr(10).join('      ' + x for x in tweens).lstrip()}
      tl.fromTo("#escuro", {{ opacity: 0 }}, {{ opacity: 1, duration: {FADE_FINAL}, ease: "none", immediateRender: false }}, {total - FADE_FINAL});
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
"""
    (hf / "index.html").write_text(doc, encoding="utf-8")
    print(f"{len(tomadas)} tomadas, {len(audios)} trechos de fala, {len(legs)} legendas, "
          f"duração {total:.1f}s ({int(total // 60)}:{int(total % 60):02d})")
    for ato, ini in ordem:
        print(f"  {ato}: começa em {int(ini // 60)}:{int(ini % 60):02d}")


if __name__ == "__main__":
    main()
