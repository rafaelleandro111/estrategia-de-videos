# Gera um Short (9:16) a partir de um trecho ja montado (build/segNN.mp4, ja em P&B e com audio nivelado).
# Uso: python -I corte_vertical.py <pasta-do-video> <n-do-trecho> "<TITULO DO TOPO>" [zoom] [desloc_x] [desloc_y] [gamma]
#   zoom: 1.0 = recorte 9:16 do centro; 1.4 = 40% mais perto (pra quem aparece pequeno no palco)
#   desloc_x: -0.2 a 0.2, move o recorte pra esquerda/direita (fracao da largura)
#   desloc_y: negativo sobe o recorte (com zoom, pra nao cortar a cabeca); gamma > 1 clareia palco escuro
# Opcoes nomeadas (depois do titulo, em qualquer ordem):
#   faixa      cena inteira no meio da tela, fundo preto (pra cena de serie com 2 pessoas, licao 26)
#   de=S ate=S usa so esse pedaco do trecho (segundos dentro do segNN). Short com claim e > 60s e bloqueado
# Saida: <pasta-do-video>/cortes/corte-<n>.mp4. Licoes em LICOES.md
import json, os, subprocess, sys
import numpy as np
from faster_whisper import WhisperModel

PASTA, N, TITULO = sys.argv[1], int(sys.argv[2]), sys.argv[3]
_pos = [a for a in sys.argv[4:] if "=" not in a and a != "faixa"]
OPT = dict(a.split("=", 1) for a in sys.argv[4:] if "=" in a)
FAIXA = "faixa" in sys.argv[4:]
ZOOM = float(_pos[0]) if len(_pos) > 0 else 1.0
DX = float(_pos[1]) if len(_pos) > 1 else 0.0
DY = float(_pos[2]) if len(_pos) > 2 else 0.0
GAMMA = float(_pos[3]) if len(_pos) > 3 else 1.0
seg = os.path.join(PASTA, "build", f"seg{N - 1:02d}.mp4")
tr = next(t for t in json.load(open(os.path.join(PASTA, "trechos.json"), encoding="utf-8")) if t["n"] == N)
saida_dir = os.path.join(PASTA, "cortes"); os.makedirs(saida_dir, exist_ok=True)
tmp = os.path.join(saida_dir, f"_corte-{N:02d}")
os.makedirs(tmp, exist_ok=True)

FORTES = {"medo", "coragem", "avance", "desistir", "fracassar", "fracasso", "desculpas", "conforto",
          "mudança", "mudar", "tempo", "agora", "cérebro", "procrastinação", "nunca", "filhos"}


def run(cmd):
    r = subprocess.run(cmd, creationflags=0x4000, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stderr[-2000:]); raise SystemExit("ffmpeg falhou")


dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", seg],
                           capture_output=True, text=True).stdout)
DE = float(OPT.get("de", 0)); ATE = float(OPT.get("ate", dur))
if DE > 0 or ATE < dur:  # pedaco do trecho: corta pra um arquivo temporario e segue com ele
    parte = os.path.join(tmp, "parte.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-ss", f"{DE:.2f}", "-to", f"{ATE:.2f}", "-i", seg,
         "-af", f"afade=t=in:d=0.15,afade=t=out:st={ATE - DE - 0.3:.2f}:d=0.3",
         "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", parte])
    seg, dur = parte, ATE - DE

# 1) Palavras com tempo (Whisper no proprio trecho, que ja comeca no 0)
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", seg, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
m = WhisperModel("medium", device="cpu", compute_type="int8", cpu_threads=4)
segs, _ = m.transcribe(audio, language="pt", beam_size=5, word_timestamps=True, vad_filter=False,
                       condition_on_previous_text=False)
ws = [[w.start, w.end, w.word.strip()] for s in segs for w in s.words]
for errado, certo in tr.get("corrigir", {}).items():
    for w in ws:
        if w[2].strip(".,?!").lower() == errado:
            w[2] = w[2].lower().replace(errado, certo)

# 2) Legenda ASS em pe: blocos de ate 3 palavras, quebra em pontuacao
def t_ass(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"

blocos, atual = [], []
for w in ws:
    atual.append(w)
    if len(atual) >= 3 or w[2][-1:] in ".,?!:;":
        blocos.append(atual); atual = []
if atual:
    blocos.append(atual)
linhas = []
for j, b in enumerate(blocos):
    a = b[0][0]
    z = min(blocos[j + 1][0][0] - 0.02 if j + 1 < len(blocos) else b[-1][1] + 0.4, b[-1][1] + 0.6)
    partes = []
    for w in b:
        limpa = w[2].strip(".,?!:;\"'“”…").upper()
        if limpa:
            partes.append(r"{\fs120}" + limpa + r"{\fs86}" if limpa.lower() in FORTES else limpa)
    if partes:
        linhas.append(f"Dialogue: 0,{t_ass(a)},{t_ass(z)},Fala,,0,0,0,,{{\\pos(540,1340)\\fad(80,50)}}{' '.join(partes)}")
ass = os.path.join(tmp, "legenda.ass")
with open(ass, "w", encoding="utf-8") as f:
    f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding\n"
            "Style: Fala,Georgia,86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,1,0,1,2,3,5,60,60,0,1\n"
            "Style: Topo,Georgia,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,2,0,1,2,3,8,70,70,170,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    f.write(f"Dialogue: 1,{t_ass(0)},{t_ass(dur)},Topo,,0,0,0,,{{\\fad(300,300)}}{TITULO}\n")
    f.write("\n".join(linhas) + "\n")

# 3) Video: recorte 9:16 (com zoom/deslocamento), musica com ducking, legenda
cw = f"ih*9/16/{ZOOM}"
ch = f"ih/{ZOOM}"
cx = f"(iw-{cw})/2+iw*{DX}"
cy = f"(ih-{ch})/2+ih*{DY}"
musica = os.path.join(PASTA, "musica", "musica.mp3")
if FAIXA:
    video = (f"color=c=black:s=1080x1920:d={dur:.2f}:r=30[bg];[0:v]scale=1080:-2:flags=lanczos,setsar=1,"
             f"eq=gamma={GAMMA}[cena];[bg][cena]overlay=0:(H-h)/2:shortest=1,")
else:
    video = f"[0:v]crop={cw}:{ch}:{cx}:{cy},scale=1080:1920:flags=lanczos,setsar=1,eq=gamma={GAMMA},"
fc = (video +
      f"subtitles={os.path.basename(ass)}:fontsdir=C\\\\:/Windows/Fonts[v];"
      f"[1:a]atrim=0:{dur:.2f},asetpts=PTS-STARTPTS,volume=0.42,afade=t=in:d=1.5,"
      f"afade=t=out:st={max(0, dur - 2):.2f}:d=2[mus];"
      "[0:a]asplit=2[voz][sc];[mus][sc]sidechaincompress=threshold=0.04:ratio=4:attack=120:release=350[musd];"
      "[voz][musd]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
out = os.path.join(saida_dir, f"corte-{N:02d}.mp4")
r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", os.path.abspath(seg), "-i", os.path.abspath(musica),
                    "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", os.path.abspath(out) + ".tmp.mp4"],
                   cwd=tmp, creationflags=0x4000, capture_output=True, text=True, encoding="utf-8", errors="replace")
if r.returncode != 0:
    print(r.stderr[-2000:]); raise SystemExit("render falhou")
os.replace(out + ".tmp.mp4", out)
print(f"pronto: {out} ({dur:.1f}s)")
