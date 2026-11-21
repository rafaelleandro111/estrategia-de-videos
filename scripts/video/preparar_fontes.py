"""Trata as cenas baixadas pra edição: área útil sem faixa preta e sem marca d'água, 16:9 cheio, limpeza e cor do canal.

Uso:
    python scripts/video/preparar_fontes.py marketing/youtube/<pasta-do-video> [--paralelo 4]

Lê <pasta>/fontes/areas.json: {"<id>": [x, y, w, h], ...} = retângulo útil de cada fonte, já sem a faixa
preta embutida e sem a faixa de baixo onde fica a marca d'água do canal de origem. O script recorta o maior
16:9 centralizado dentro dele e amplia pra 1920x1080. Saída em <pasta>/hf/media/<id>.mp4 (vídeo tratado)
e <pasta>/hf/media/<id>.m4a (som original, pra usar separado da imagem). Pula o que já existe.
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

W, H = 1920, 1080
# limpeza da compressão do YouTube + nitidez + cor do canal (contraste, cor viva, pele quente, sombra fria)
FILTRO = ("hqdn3d=1.5:1.5:6:6,deband,{crop},scale=1920:1080:flags=lanczos,setsar=1,"
          "cas=0.6,eq=contrast=1.08:saturation=1.10:brightness=0.01,"
          "colorbalance=rs=-0.02:bs=0.03:rh=0.04:bh=-0.03")


def crop_169(x, y, w, h):
    if w / h > W / H:
        nw = round(h * W / H / 2) * 2
        return f"crop={nw}:{h}:{x + (w - nw) // 2}:{y}"
    nh = round(w * H / W / 2) * 2
    return f"crop={w}:{nh}:{x}:{y + (h - nh) // 2}"


def tratar(fontes, media, id_, area, preset="medium"):
    mp4, m4a = media / f"{id_}.mp4", media / f"{id_}.m4a"
    src = fontes / f"{id_}.mp4"
    if not mp4.exists():
        tmp = mp4.with_suffix(".tmp.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", FILTRO.format(crop=crop_169(*area)),
                        "-an", "-c:v", "libx264", "-preset", preset, "-crf", "16", "-pix_fmt", "yuv420p",
                        "-g", "24", "-movflags", "+faststart", tmp], check=True)
        tmp.rename(mp4)
    if not m4a.exists():
        # volume igualado entre as fontes (cada canal de cenas sobe num volume diferente)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-af", "loudnorm=I=-20:TP=-2:LRA=11",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", m4a], check=True)
    return id_


def main():
    pasta = Path(sys.argv[1]).resolve()
    n = int(sys.argv[sys.argv.index("--paralelo") + 1]) if "--paralelo" in sys.argv else 4
    fontes, media = pasta / "fontes", pasta / "hf" / "media"
    media.mkdir(parents=True, exist_ok=True)
    nome = sys.argv[sys.argv.index("--areas") + 1] if "--areas" in sys.argv else "areas.json"
    preset = "veryfast" if "--rapido" in sys.argv else "medium"
    areas = json.loads((fontes / nome).read_text(encoding="utf-8"))
    with ThreadPoolExecutor(n) as ex:
        for id_ in ex.map(lambda kv: tratar(fontes, media, *kv, preset=preset), areas.items()):
            print("ok", id_, flush=True)


if __name__ == "__main__":
    main()
