"""Monta um edit de personagem (cenas dubladas + filtro do canal + música + legenda) a partir de um edit.json.

Uso:
    python scripts/video/edit_personagem.py marketing/youtube/<pasta-do-video>
    python scripts/video/edit_personagem.py marketing/youtube/<pasta-do-video> --previa   # 540p rápido pra conferir

Regras do canal aplicadas aqui (ver _memoria/preferencias.md):
  - sem corte seco: toda passagem escurece e entra (fadeblack), e as falas se misturam na passagem
  - música em ~90% nas cenas sem fala e ~35% durante as falas; voz um pouco mais baixa
  - troca de música no ato de virada/superação (crossfade)
  - faixas pretas de cinema 2.39:1 (cobrem marca d'água) e legenda dentro da faixa de baixo
  - filtro de cor padrão do canal (FILTRO_CANAL)

edit.json: {"transicao": 0.8, "musicas": {"triste": {...}, "superacao": {...}}, "cenas": [...]}
cada cena: {"ato": "tristeza|virada|superacao", "src": "<id em fontes/>", "ini": s, "fim": s,
            "modo": "fala|mudo|acao", "legenda": [[ini, fim, "texto"], ...]}
A música "superacao" entra na primeira cena que não for do ato "tristeza".
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 48000
FPS = 30
W, H = 2560, 1440  # 1440p: o YouTube entrega com codec melhor (VP9), fica mais nítido que 1080p
FAIXA = round((H - W / 2.39) / 2)  # altura de cada faixa preta

# limpeza antes de ampliar: tira o ruído e os blocos da compressão do YouTube
FILTRO_LIMPEZA = "hqdn3d=1.5:1.5:6:6,deband"
# filtro padrão do canal (depois de ampliar): nitidez, contraste e cor mais viva, sombras frias e pele quente
FILTRO_CANAL = ("cas=0.7,eq=contrast=1.10:saturation=1.12:brightness=0.02,"
                "colorbalance=rs=-0.02:bs=0.03:rh=0.04:bh=-0.03,"
                "vignette=angle=PI/6")

GANHO = {"fala": 0.85, "mudo": 0.0, "acao": 0.30}  # voz/som original por modo (após normalizar)
MUSICA_SEM_FALA, MUSICA_COM_FALA = 0.90, 0.35
ALVO_DB = -20.0


def run(cmd, cwd=None):
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def duracao(arq):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def ler_audio(arq, ini=None, fim=None):
    cmd = ["ffmpeg", "-v", "error"]
    if ini is not None:
        cmd += ["-ss", f"{ini:.3f}", "-to", f"{fim:.3f}"]
    cmd += ["-i", str(arq), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def rms_ativo(a):
    """RMS só dos trechos com som (ignora silêncio), em dB."""
    m = a.mean(axis=1)
    janela = SR // 10
    n = len(m) // janela
    if n == 0:
        return -90.0
    r = np.sqrt((m[: n * janela].reshape(n, janela) ** 2).mean(axis=1))
    r = r[r > np.percentile(r, 50)]
    return 20 * np.log10(r.mean() + 1e-9) if len(r) else -90.0


def rampa(a, ent, sai):
    n = len(a)
    ent, sai = min(int(ent * SR), n // 2), min(int(sai * SR), n // 2)
    if ent:
        a[:ent] *= np.linspace(0, 1, ent)[:, None]
    if sai:
        a[n - sai:] *= np.linspace(1, 0, sai)[:, None]
    return a


def suavizar(env, seg):
    """Média móvel de `seg` segundos (calculada a cada 100 amostras e interpolada de volta)."""
    e = env[::100]
    k = max(1, int(seg * SR / 100))
    e = np.convolve(np.pad(e, (k, k), mode="edge"), np.ones(k) / k, mode="same")[k:-k]
    return np.interp(np.arange(len(env)), np.arange(len(e)) * 100, e).astype(np.float32)


def tempo_ass(t):
    h, r = divmod(max(t, 0), 3600)
    m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def main():
    pasta = Path(sys.argv[1]).resolve()
    previa = "--previa" in sys.argv
    cfg = json.loads((pasta / "edit.json").read_text(encoding="utf-8"))
    d = cfg.get("transicao", 0.8)
    cenas = cfg["cenas"]
    build = pasta / "build"
    build.mkdir(exist_ok=True)

    # nunca pedir além do fim da fonte (senão a cadeia de transições quebra e o resto fica preto)
    for c in cenas:
        c["fim"] = min(c["fim"], duracao(pasta / "fontes" / f"{c['src']}.mp4") - 0.1)

    # linha do tempo: cada cena começa d segundos antes da anterior terminar
    t, inicio = 0.0, []
    for c in cenas:
        inicio.append(t)
        t += (c["fim"] - c["ini"]) - d
    total = t + d

    # ---------------------------------------------------------- 1. cada cena com filtro + faixas
    larg, alt = (960, 540) if previa else (W, H)
    faixa = round(FAIXA * alt / H)
    for i, c in enumerate(cenas):
        saida = build / f"cena{i:02d}{'-p' if previa else ''}.mp4"
        vf = (f"{FILTRO_LIMPEZA},scale={larg}:{alt}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop={larg}:{alt},setsar=1,fps={FPS},"
              f"{FILTRO_CANAL},"
              + (f"eq=gamma={c['clarear']}:brightness=0.03," if c.get('clarear') else "")  # cena escura demais
              + "format=yuv420p,"
              f"drawbox=x=0:y=0:w=iw:h={faixa}:color=black:t=fill,"
              f"drawbox=x=0:y=ih-{faixa}:w=iw:h={faixa}:color=black:t=fill")
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{c['ini']:.3f}", "-to", f"{c['fim']:.3f}",
             "-i", pasta / "fontes" / f"{c['src']}.mp4", "-vf", vf, "-an",
             "-c:v", "libx264", "-preset", "veryfast" if previa else "medium", "-crf", "26" if previa else "17", saida])
        print(f"cena {i + 1}/{len(cenas)} ok", flush=True)

    # ---------------------------------------------------------- 2. áudio: falas + música com ducking
    mix = np.zeros((int((total + 1) * SR), 2), np.float32)
    fala = np.zeros(len(mix), np.float32)
    for i, c in enumerate(cenas):
        g = GANHO[c["modo"]]
        if g == 0:
            continue
        a = ler_audio(pasta / "fontes" / f"{c['src']}.mp4", c["ini"], c["fim"])
        a *= 10 ** ((ALVO_DB - rms_ativo(a)) / 20) * g
        a = rampa(a, 0.15, 0.25)
        p = int(inicio[i] * SR)
        mix[p:p + len(a)] += a[: len(mix) - p]
        if c["modo"] == "fala":
            for s, e, _ in c.get("legenda", []):
                fala[int((inicio[i] + s - c["ini"] - 0.3) * SR):int((inicio[i] + e - c["ini"] + 0.3) * SR)] = 1

    env = suavizar(MUSICA_SEM_FALA - (MUSICA_SEM_FALA - MUSICA_COM_FALA) * fala, 0.5)
    i_troca = next(i for i, c in enumerate(cenas) if c["ato"] != "tristeza")
    t_troca = inicio[i_troca]
    musica = np.zeros_like(mix)
    for nome, de, ate, ent, sai in (("triste", 0.0, t_troca + 2.0, 1.5, 3.5),
                                    ("superacao", t_troca, total, 2.5, 4.0)):
        m = cfg["musicas"][nome]
        a = ler_audio(pasta / m["arquivo"], m["inicio"], m["inicio"] + (ate - de))
        a *= 10 ** ((-18.0 - rms_ativo(a)) / 20)
        a = rampa(a, ent, sai)
        p = int(de * SR)
        musica[p:p + len(a)] += a[: len(musica) - p]
    mix += musica * env[:, None]
    mix = rampa(mix[: int(total * SR)], 0.0, 2.0)
    mix *= 10 ** ((-17.0 - rms_ativo(mix)) / 20)  # volume final perto do padrão do YouTube
    mix = 0.95 * np.tanh(mix / 0.95)  # limitador suave, sem estalo
    wav = build / "mix.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s16le", str(wav)], input=mix.astype(np.float32).tobytes(), check=True)

    # ---------------------------------------------------------- 3. legenda (dentro da faixa preta de baixo)
    tam = round(44 * alt / 1080)
    ass = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {larg}", f"PlayResY: {alt}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, "
        "Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
        f"Style: Padrao,Segoe UI Semibold,{tam},&H00FFFFFF,&H00000000,&H00000000,0,0,1,{max(1, round(2 * alt / 1080))},0,2,"
        f"{round(160 * alt / 1080)},{round(160 * alt / 1080)},{round(faixa / 2 - tam / 2)}",
        "", "[Events]", "Format: Layer, Start, End, Style, Text",
    ]
    falas = sorted((inicio[i] + s - c["ini"], inicio[i] + min(e, c["fim"]) - c["ini"], txt)
                   for i, c in enumerate(cenas) for s, e, txt in c.get("legenda", []))
    for k, (a0, a1, txt) in enumerate(falas):
        if k + 1 < len(falas):  # na passagem entre cenas, a legenda anterior sai quando a próxima entra
            a1 = min(a1, falas[k + 1][0] - 0.05)
        ass.append(f"Dialogue: 0,{tempo_ass(a0)},{tempo_ass(a1)},Padrao,{{\\fad(120,120)}}{txt}")
    (build / "legenda.ass").write_text("\n".join(ass), encoding="utf-8")

    # ---------------------------------------------------------- 4. junta tudo com fadeblack + legenda + áudio
    entradas, grafo, ant = [], [], "0:v"
    for i in range(len(cenas)):
        entradas += ["-i", f"cena{i:02d}{'-p' if previa else ''}.mp4"]
    for i in range(1, len(cenas)):
        sai = f"x{i}"
        grafo.append(f"[{ant}][{i}:v]xfade=transition=fadeblack:duration={d}:offset={inicio[i]:.3f}[{sai}]")
        ant = sai
    grafo.append(f"[{ant}]fade=t=in:st=0:d=1.2,fade=t=out:st={total - 2:.3f}:d=2,"
                 f"subtitles=legenda.ass:fontsdir=C\\\\:/Windows/Fonts[v]")
    saida = pasta / (("previa-" if previa else "") + cfg.get("saida", "video-final.mp4"))
    run(["ffmpeg", "-v", "error", "-stats", "-y", *entradas, "-i", "mix.wav",
         "-filter_complex", ";".join(grafo), "-map", "[v]", "-map", f"{len(cenas)}:a",
         "-c:v", "libx264", "-preset", "veryfast" if previa else "medium", "-crf", "26" if previa else "18",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", saida],
        cwd=build)
    print(f"\npronto: {saida}  ({total:.1f}s)  troca de música em {t_troca:.1f}s")


if __name__ == "__main__":
    main()
