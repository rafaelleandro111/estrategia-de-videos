"""Modo voz própria: troca a tua voz da gravação pela voz IA do canal.

Passo 1 — transcrever (gera fala.txt pra você revisar):
    python scripts/video/voz_propria.py <pasta> transcrever
Passo 2 — dublar (lê fala.txt, gera a voz IA e ajusta o vídeo):
    python scripts/video/voz_propria.py <pasta> dublar

A gravação fica em <pasta>/gravacoes/bruto.mp4 (ou passe --video arquivo.mp4).
Opcional: --som-original 0.2 mantém o som da gravação baixinho (só faz sentido se
a tua voz estiver numa trilha separada do som do jogo/tela).
Saída: <pasta>/dublado.mp4 e <pasta>/dublado-palavras.json (tempo das palavras, pra legenda).

Em fala.txt, cada linha é uma frase: "[inicio-fim] texto". Pode corrigir o texto
à vontade (tirar "é...", "tipo", trocar palavra); não mexa nos números entre colchetes.
Apague a linha inteira pra cortar a frase da narração.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from montar import narrar, run  # noqa: E402
from palavras import ffmpeg_bin, transcrever  # noqa: E402

PAUSA = 0.7      # silêncio (s) que separa uma frase da outra
FPS = 60


def frases_de(palavras):
    frases, atual = [], []
    for i, w in enumerate(palavras):
        atual.append(w)
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        if prox is None or prox["start"] - w["end"] > PAUSA or re.search(r"[.?!]$", w["text"]):
            frases.append({"inicio": atual[0]["start"], "fim": atual[-1]["end"],
                           "texto": " ".join(x["text"] for x in atual)})
            atual = []
    return frases


def ler_fala(arq):
    frases = []
    for linha in arq.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*\[([\d.]+)-([\d.]+)\]\s*(.*)", linha)
        if m and m.group(3).strip():
            frases.append({"inicio": float(m.group(1)), "fim": float(m.group(2)), "texto": m.group(3).strip()})
    return frases


def duracao(video):
    ffprobe = str(Path(ffmpeg_bin()).with_name("ffprobe.exe")) if ffmpeg_bin().endswith(".exe") else "ffprobe"
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def transcrever_cmd(pasta, video):
    frases = frases_de(transcrever(str(video)))
    linhas = [f"[{f['inicio']:.2f}-{f['fim']:.2f}] {f['texto']}" for f in frases]
    (pasta / "fala.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("\n".join(linhas))
    print(f"\n{len(frases)} frases -> {pasta / 'fala.txt'}  (revise o texto e rode 'dublar')")


def dublar_cmd(pasta, video, voz, manter_som=0.0):
    """O vídeo fica na velocidade original; cada frase da voz IA entra onde você falou.
    Se uma frase IA invadir a próxima, a próxima espera a anterior terminar."""
    frases = ler_fala(pasta / "fala.txt")
    total = duracao(video)
    vozes, palavras_saida, livre = [], [], 0.0
    for i, f in enumerate(frases):
        wav, d_voz, pal = narrar(f["texto"], f"frase{i + 1:03d}", pasta / "audio", voz)
        quando = max(f["inicio"], livre)
        vozes.append((wav, quando))
        palavras_saida += [{"text": p["text"], "start": round(p["start"] + quando, 3),
                            "end": round(p["end"] + quando, 3)} for p in pal]
        livre = quando + d_voz + 0.15
    fim = max(total, livre)

    entradas = ["-i", str(video)]
    fc, mix = [], []
    for j, (wav, quando) in enumerate(vozes):
        entradas += ["-i", str(wav)]
        ms = int(quando * 1000)
        fc.append(f"[{j + 1}:a]aresample=48000,adelay={ms}|{ms}[a{j}]")
        mix.append(f"[a{j}]")
    if manter_som > 0:  # som original baixinho (atenção: inclui a tua voz se ela estiver na mesma trilha)
        fc.append(f"[0:a]volume={manter_som}[orig]")
        mix.append("[orig]")
    fc.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0,apad,atrim=0:{fim:.3f}[a]")
    fc.append(f"[0:v]fps={FPS},tpad=stop_mode=clone:stop_duration={max(0, fim - total):.3f}[v]")
    saida = pasta / "dublado.mp4"
    run([ffmpeg_bin(), "-y", "-v", "error", *entradas, "-filter_complex", ";".join(fc),
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", saida])
    (pasta / "dublado-palavras.json").write_text(json.dumps(palavras_saida, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    print(f"\npronto: {saida}  ({fim:.1f} s)")


if __name__ == "__main__":
    pasta = Path(sys.argv[1]).resolve()
    acao = sys.argv[2] if len(sys.argv) > 2 else "transcrever"
    video = Path(sys.argv[sys.argv.index("--video") + 1]) if "--video" in sys.argv else pasta / "gravacoes" / "bruto.mp4"
    voz = sys.argv[sys.argv.index("--voz") + 1] if "--voz" in sys.argv else "pm_santa"
    if acao == "transcrever":
        transcrever_cmd(pasta, video)
    elif acao == "dublar":
        som = float(sys.argv[sys.argv.index("--som-original") + 1]) if "--som-original" in sys.argv else 0.0
        dublar_cmd(pasta, video, voz, som)
    else:
        sys.exit("ação desconhecida: use 'transcrever' ou 'dublar'")
