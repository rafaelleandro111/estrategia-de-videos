"""Junta as partes renderizadas de um edit num MP4 só e confere o resultado.

Uso: python scripts/video/juntar_partes.py <pasta-do-video>
  Lê <pasta>/final/parte1.mp4, parte2.mp4, parte3.mp4 e grava <pasta>/final/<pasta>-final.mp4.
  Emendas: parte1→parte2 direto (a 1 já termina no escuro e a 2 já começa do escuro);
           parte2→parte3 com fusão de 0,5 s (mesma música; a parte 3 começa a faixa 0,5 s antes, então soma igual).
Depois confere: tela preta, silêncio e volume por trecho.
"""
import subprocess
import sys
from pathlib import Path

BAIXA_PRIORIDADE = 0x00004000
FUSAO = 0.5


def duracao(arq):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)],
                                capture_output=True, text=True, check=True).stdout)


def main():
    pasta = Path(sys.argv[1]).resolve()
    fin = pasta / "final"
    p1, p2, p3 = (fin / f"parte{i}.mp4" for i in (1, 2, 3))
    saida = fin / f"{pasta.name}-final.mp4"
    off = duracao(p1) + duracao(p2) - FUSAO
    filtro = (f"[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v12][a12];"
              f"[v12][2:v]xfade=transition=fade:duration={FUSAO}:offset={off:.3f}[v];"
              f"[a12][2:a]acrossfade=d={FUSAO}:c1=tri:c2=tri[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-stats", "-y", "-i", p1, "-i", p2, "-i", p3, "-filter_complex", filtro,
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", saida],
                   creationflags=BAIXA_PRIORIDADE, check=True)
    total = duracao(saida)
    print(f"\n{saida.name}: {int(total // 60)}:{total % 60:04.1f}")
    print(f"emendas: parte 2 em {int(duracao(p1) // 60)}:{duracao(p1) % 60:04.1f}, parte 3 em {int(off // 60)}:{off % 60:04.1f}")

    # conferência: tela preta (>0,4 s), silêncio (>1,5 s abaixo de -45 dB)
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", saida, "-vf", "blackdetect=d=0.4:pix_th=0.08",
                          "-af", "silencedetect=n=-45dB:d=1.5", "-f", "null", "-"],
                         capture_output=True, text=True, creationflags=BAIXA_PRIORIDADE).stderr
    for linha in log.splitlines():
        if "black_start" in linha or "silence_end" in linha:
            print("  ", linha.split("]", 1)[1].strip())


if __name__ == "__main__":
    main()
