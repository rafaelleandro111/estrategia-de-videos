"""Monta um vídeo do canal a partir de uma pasta com video.json.

Uso:
    python scripts/video/montar.py marketing/youtube/<pasta-do-video>            # monta e renderiza
    python scripts/video/montar.py marketing/youtube/<pasta-do-video> --so-montar  # só monta (pra ver no preview)

O que faz, sem precisar do Claude:
  1. gera a narração de cada bloco com o Kokoro (cache: só regera se o texto mudar)
  2. tira o tempo de cada palavra (legenda)
  3. corta/acelera cada gravação de tela pra caber na narração do trecho
  4. escreve o index.html com as peças do template (scripts/template-video/compositions)
  5. renderiza o MP4 em <pasta-do-video>/video-final.mp4
"""
import hashlib
import html
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from palavras import ffmpeg_bin, transcrever  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
TEMPLATE = RAIZ / "scripts" / "template-video"
FPS = 30


def npx():
    return shutil.which("npx") or "npx"


def run(cmd, cwd=None):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def duracao_wav(p):
    with wave.open(str(p)) as w:
        return w.getnframes() / w.getframerate()


def duracao_midia(p):
    ffprobe = str(Path(ffmpeg_bin()).with_name("ffprobe.exe")) if ffmpeg_bin().endswith(".exe") else "ffprobe"
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


# ---------------------------------------------------------------- narração

def narrar(texto, nome, pasta_audio, voz):
    """Gera (ou reaproveita) a narração de um bloco. Devolve (wav, duração, palavras)."""
    pasta_audio.mkdir(parents=True, exist_ok=True)
    chave = hashlib.sha1(f"{voz}|{texto}".encode("utf-8")).hexdigest()[:10]
    wav = pasta_audio / f"{nome}-{chave}.wav"
    pal = wav.with_suffix(".json")
    if not wav.exists():
        txt = wav.with_suffix(".txt")
        txt.write_text(texto, encoding="utf-8")
        run([npx(), "-y", "hyperframes", "tts", txt, "--voice", voz, "--output", wav])
    if not pal.exists():
        palavras = transcrever(str(wav))
        # o Whisper às vezes ouve errado ("pra gente" no lugar de "pro agente");
        # quando a contagem bate, usa a grafia do roteiro com o tempo do Whisper
        tokens = texto.split()
        if len(tokens) == len(palavras):
            for p, t in zip(palavras, tokens):
                p["text"] = t
        pal.write_text(json.dumps(palavras, ensure_ascii=False), encoding="utf-8")
    return wav, duracao_wav(wav), json.loads(pal.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- gravação

def preparar_gravacao(origem, inicio, fim, alvo, saida):
    """Corta [inicio, fim] da gravação e acelera/estica pra durar exatamente `alvo` segundos."""
    total = duracao_midia(origem)
    fim = total if fim is None else min(fim, total)
    trecho = max(0.1, fim - inicio)
    vel = trecho / alvo
    filtros = [f"setpts=PTS/{vel:.4f}"] if vel > 1 else []
    if vel < 1:  # gravação mais curta que a fala: segura o último quadro
        filtros.append(f"tpad=stop_mode=clone:stop_duration={alvo - trecho:.3f}")
    filtros += ["scale=1920:1080:force_original_aspect_ratio=decrease",
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0A0F0B", f"fps={FPS}"]
    run([ffmpeg_bin(), "-y", "-v", "error", "-ss", f"{inicio:.3f}", "-to", f"{fim:.3f}", "-i", origem,
         "-vf", ",".join(filtros), "-t", f"{alvo:.3f}", "-an",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20", saida])


# ---------------------------------------------------------------- html

def host(comp, inicio, dur, valores, faixa=1):
    vv = html.escape(json.dumps(valores, ensure_ascii=False), quote=True)
    id_ = f"{comp}-{inicio:.2f}".replace(".", "-")
    return (f'<div id="{id_}" data-composition-id="{comp}" '
            f'data-composition-src="compositions/{comp}.html" data-start="{inicio:.3f}" '
            f'data-duration="{dur:.3f}" data-track-index="{faixa}" data-width="1920" data-height="1080" '
            f"data-variable-values=\"{vv}\"></div>")


def audio(id_, src, inicio, dur):
    return (f'<audio id="{id_}" src="{src}" data-start="{inicio:.3f}" data-duration="{dur:.3f}" '
            f'data-track-index="5" data-volume="1"></audio>')


def segundos(txt):
    """'06:12' -> 372 ; números passam direto."""
    if isinstance(txt, (int, float)):
        return float(txt)
    m, s = txt.split(":")
    return int(m) * 60 + float(s)


def montar(pasta):
    cfg = json.loads((pasta / "video.json").read_text(encoding="utf-8"))
    voz = cfg.get("voz", "pm_santa")
    build = pasta / "build"
    if build.exists():
        shutil.rmtree(build / "compositions", ignore_errors=True)
    (build / "assets").mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE / "compositions", build / "compositions")
    for f in ("hyperframes.json", "package.json", "meta.json"):
        shutil.copy(TEMPLATE / f, build / f)
    shutil.copy(TEMPLATE / "assets" / "gravacao-exemplo.mp4", build / "assets")  # reserva do template
    pasta_audio = pasta / "audio"

    clips, audios, t = [], [], 0.0
    n_audio = 0

    def fala(texto, nome, quando):
        nonlocal n_audio
        if not texto:
            return 0.0, []
        wav, d, pal = narrar(texto, nome, pasta_audio, voz)
        destino = build / "assets" / wav.name
        shutil.copy(wav, destino)
        n_audio += 1
        audios.append(audio(f"vo-{n_audio}", f"assets/{wav.name}", quando, d))
        return d, pal

    # abertura
    ab = cfg["abertura"]
    d_ab = fala(ab.get("narracao"), "abertura", t + 0.4)[0]
    dur = max(5.0, d_ab + 1.0)
    clips.append(host("abertura", t, dur, {"ia": cfg["ia"], "titulo": ab["titulo"],
                                           "titulo_destaque": ab.get("titulo_destaque", ""),
                                           "subtitulo": ab.get("subtitulo", "")}))
    t += dur

    placar = []
    for nv in cfg["niveis"]:
        n = nv["numero"]
        # cartela
        d = fala(nv.get("narracao_cartela"), f"nivel{n}-cartela", t + 0.5)[0]
        dur = max(3.0, d + 1.2)
        clips.append(host("cartela-nivel", t, dur, {"numero": n, "desafio": nv["desafio"],
                                                    "dificuldade": nv.get("dificuldade", n)}))
        t += dur
        # trechos de gravação
        crono_de, crono_ate = segundos(nv.get("crono_de", 0)), segundos(nv.get("crono_ate", 0))
        trechos = nv["trechos"]
        passo = (crono_ate - crono_de) / max(1, len(trechos))
        for i, tr in enumerate(trechos):
            d, pal = fala(tr["narracao"], f"nivel{n}-trecho{i + 1}", t + 0.3)
            dur = d + 0.7
            nome_mp4 = f"nivel{n}-trecho{i + 1}.mp4"
            preparar_gravacao(pasta / tr["gravacao"], tr.get("inicio", 0), tr.get("fim"), dur,
                              build / "assets" / nome_mp4)
            legenda = [{"text": p["text"], "start": round(p["start"] + 0.3, 3), "end": round(p["end"] + 0.3, 3)}
                       for p in pal]
            clips.append(host("tela-agente", t, dur, {
                "gravacao": f"assets/{nome_mp4}", "ia": cfg["ia"], "numero": n, "duracao": round(dur, 3),
                "crono_de": crono_de + passo * i, "crono_ate": crono_de + passo * (i + 1),
                "legenda": json.dumps(legenda, ensure_ascii=False),
                "zooms": json.dumps(tr.get("zooms", []))}))
            t += dur
        # veredito
        vd = nv["veredito"]
        d = fala(vd.get("narracao"), f"nivel{n}-veredito", t + 0.45)[0]
        dur = max(3.0, d + 1.2)
        clips.append(host("veredito", t, dur, {"resultado": vd["resultado"], "numero": n,
                                               "tempo": vd.get("tempo", ""), "comentario": vd.get("comentario", "")}))
        t += dur
        placar.append({"numero": n, "desafio": nv.get("nome_curto", nv["desafio"].title()),
                       "resultado": vd["resultado"], "tempo": vd.get("tempo", "")})

    # placar final
    fim_cfg = cfg.get("encerramento", {})
    d = fala(fim_cfg.get("narracao"), "encerramento", t + 0.6)[0]
    dur = max(5.0, d + 1.5)
    clips.append(host("placar", t, dur, {"niveis": json.dumps(placar, ensure_ascii=False),
                                         "pergunta": fim_cfg.get("pergunta", "QUAL IA EU TESTO AGORA?")}))
    t += dur

    corpo = "\n      ".join(clips + audios)
    index = f"""<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: 1920px; height: 1080px; overflow: hidden; background: #0A0F0B; }}
      #root {{ position: relative; width: 100%; height: 100%; background: #0A0F0B; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{t:.3f}" data-width="1920" data-height="1080">
      {corpo}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
    (build / "index.html").write_text(index, encoding="utf-8")
    print(f"\nmontado: {build / 'index.html'}  ({t:.1f} s)")
    return build, t


if __name__ == "__main__":
    pasta = Path(sys.argv[1]).resolve()
    build, total = montar(pasta)
    if "--so-montar" not in sys.argv:
        saida = pasta / "video-final.mp4"
        run([npx(), "-y", "hyperframes", "render", "--output", saida], cwd=build)
        print(f"\npronto: {saida}")
