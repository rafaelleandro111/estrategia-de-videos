# Monta um video de falas (formato So uma chance) a partir dos trechos escolhidos.
# Uso: python -I montar.py <pasta-do-video> <pasta-transcricoes> [teste]
# Le <pasta-do-video>/trechos.json, fontes em fontes/, musica em musica/musica.mp3. Licoes em LICOES.md
import json, os, subprocess, sys

PASTA = sys.argv[1]
TRANS = sys.argv[2]
TESTE = len(sys.argv) > 3
FONTES = os.path.join(PASTA, "fontes")
BUILD = os.path.join(PASTA, "build")
os.makedirs(BUILD, exist_ok=True)

# Usa a placa de video (NVENC) se o driver permitir; senao, processador
def _nvenc_ok():
    r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=s=1920x1080:d=0.2",
                        "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True)
    return r.returncode == 0
if _nvenc_ok():
    ENC_SEG = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19"]
    ENC_FINAL = ["-c:v", "h264_nvenc", "-preset", "p6", "-cq", "21", "-b:v", "0"]
    print("encoder: placa de video (NVENC)", flush=True)
else:
    ENC_SEG = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
    ENC_FINAL = ["-c:v", "libx264", "-preset", "fast", "-crf", "21"]
    print("encoder: processador (atualize o driver NVIDIA pra usar a placa)", flush=True)

# Folgas curtas: com 1.0/1.2/0.8 sobrava ~1.4s sem voz entre trechos (licao 17)
XF = 0.5          # duracao do dissolve entre trechos
PAD_ANTES = 0.35  # folga antes da primeira palavra
PAD_DEPOIS = 0.55 # folga depois da ultima palavra

# (fonte, inicio aproximado, fim aproximado): o script ajusta pra comeco/fim de frase
TRECHOS = json.load(open(os.path.join(PASTA, "trechos.json"), encoding="utf-8"))

# config.json opcional na pasta do video: {"cor": "<filtros de cor>"}. Sem ele, o P&B escuro padrao do canal
_cfg = os.path.join(PASTA, "config.json")
CFG = json.load(open(_cfg, encoding="utf-8")) if os.path.exists(_cfg) else {}
COR = CFG.get("cor", "hue=s=0,eq=contrast=1.32:brightness=-0.07:gamma=0.9,vignette=angle=PI/3.6")

PALAVRAS_FORTES = {"medo", "medos", "coragem", "avance", "covarde", "pânico", "levanta", "levante",
                   "luta", "desafio", "mornos", "imaginado", "paralisante", "enfrentar", "desistir",
                   "tristeza", "atue", "fugir", "salvador", "fracassar", "fracasso",
                   "persistência", "recomece", "milagre", "desculpas", "treina", "merece", "agora",
                   "procrastinação", "procrastinar", "procrastinador", "adiar", "amanhã", "desconforto",
                   "conforto", "mudança", "sapo", "mediocridade", "tempo"}


def palavras(fonte):
    segs = json.load(open(os.path.join(TRANS, fonte + ".json"), encoding="utf-8"))
    return [w for s in segs for w in s["words"]]


_sil = {}
def silencios(fonte):
    # Pausas reais do audio (ffmpeg silencedetect), usadas pra cortar sem pegar fala vizinha
    if fonte not in _sil:
        r = subprocess.run(["ffmpeg", "-v", "info", "-i", os.path.join(FONTES, fonte + ".mp4"), "-vn",
                            "-af", "highpass=f=80,silencedetect=noise=-34dB:d=0.12", "-f", "null", "-"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        ini = [float(l.split("silence_start: ")[1].split()[0]) for l in r.stderr.splitlines() if "silence_start" in l]
        fim = [float(l.split("silence_end: ")[1].split()[0]) for l in r.stderr.splitlines() if "silence_end" in l]
        _sil[fonte] = list(zip(ini, fim))
    return _sil[fonte]


def pausa_perto(fonte, t, janela=0.7):
    # Pausa real mais perto do instante t (fronteira entre duas palavras segundo o Whisper)
    cand = [(min(abs(a - t), abs(b - t)) if not a <= t <= b else 0, a, b)
            for a, b in silencios(fonte) if a - janela <= t <= b + janela]
    return min(cand)[1:] if cand else None


def run(cmd):
    for tentativa in range(4):  # o ffmpeg trava as vezes (0xC0000005); tenta de novo
        r = subprocess.run(cmd, creationflags=0x4000, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            return
        print(f"  ffmpeg travou (rc {r.returncode}), tentativa {tentativa + 2}", flush=True)
    if r.returncode != 0:
        print("CMD:", " ".join(cmd)[-1500:]); print(r.stderr[-2000:])
        raise SystemExit("ffmpeg falhou")


def ass_tempo(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def blocos_legenda(ws):
    # Agrupa em blocos de ate 3 palavras, quebrando em pontuacao
    blocos, atual = [], []
    for w in ws:
        atual.append(w)
        fim_frase = w[2][-1:] in ".,?!:;"
        if len(atual) >= 3 or fim_frase:
            blocos.append(atual); atual = []
    if atual:
        blocos.append(atual)
    return blocos


def texto_bloco(bloco):
    partes = []
    for w in bloco:
        limpa = w[2].strip(".,?!:;\"'“”…").upper()
        if not limpa:
            continue
        if limpa.lower() in PALAVRAS_FORTES:
            partes.append(r"{\fs132\b1}" + limpa + r"{\fs80\b1}")
        else:
            partes.append(limpa)
    return " ".join(partes)


clips, eventos, t_global = [], [], 0.0
lista = TRECHOS[:1] if TESTE else TRECHOS
for i, tr in enumerate(lista):
    todas = palavras(tr["fonte"])
    idx = [k for k, w in enumerate(todas) if w[0] >= tr["ini"] - 0.05 and w[1] <= tr["fim"] + 0.05]
    ws = []
    for k in idx:
        w = list(todas[k])
        if w[2].startswith("-") and ws:  # "dominá" + "-lo" vira uma palavra so
            ws[-1][1] = w[1]; ws[-1][2] += w[2]
        else:
            ws.append(w)
    for errado, certo in tr.get("corrigir", {}).items():
        if " " in errado:  # varias palavras viram uma: "fingi a" -> "fingia"
            alvo = errado.split()
            k = 0
            while k <= len(ws) - len(alvo):
                if [x[2].strip(".,?!").lower() for x in ws[k:k + len(alvo)]] == alvo:
                    pont = ws[k + len(alvo) - 1][2][len(ws[k + len(alvo) - 1][2].rstrip(".,?!")):]
                    ws[k:k + len(alvo)] = [[ws[k][0], ws[k + len(alvo) - 1][1], certo + pont]]
                k += 1
            continue
        for w in ws:
            if w[2].strip(".,?!").lower() == errado:
                w[2] = w[2].lower().replace(errado, certo)
    # fronteiras de fala: meio do caminho entre a palavra vizinha e a do trecho, ajustado pra pausa real
    antes = todas[idx[0] - 1][1] if idx[0] > 0 else ws[0][0] - 2
    depois = todas[idx[-1] + 1][0] if idx[-1] + 1 < len(todas) else ws[-1][1] + 2
    p = pausa_perto(tr["fonte"], (antes + ws[0][0]) / 2)
    fala_ini = (p[1] - 0.06) if p else ws[0][0] - 0.08
    p = pausa_perto(tr["fonte"], (ws[-1][1] + depois) / 2)
    fala_fim = (p[0] + 0.08) if p else ws[-1][1] + 0.1
    if "corte_fim" in tr:  # fala emendada sem pausa: forca o corte (licao 18)
        fala_fim = min(fala_fim, tr["corte_fim"])
    # "fala_ini"/"fala_fim": ponto exato na fonte, quando o Whisper atrasa e a borda come uma palavra (licao 37)
    fala_ini = tr.get("fala_ini", fala_ini)
    fala_fim = tr.get("fala_fim", fala_fim)
    fala_ini = max(0.0, fala_ini)
    ini = max(0.0, fala_ini - PAD_ANTES)
    fim = fala_fim + PAD_DEPOIS
    dur = fim - ini
    afade = (f"afade=t=in:st={fala_ini - ini:.3f}:d=0.08,"
             f"afade=t=out:st={fala_fim - ini:.3f}:d=0.12,")
    out = os.path.join(BUILD, f"seg{i:02d}.mp4")
    nq = max(1, int(dur * 30))
    zoom = f"1+0.06*on/{nq}" if i % 2 == 0 else f"1.06-0.06*on/{nq}"
    # "recorte": fração da imagem a manter (do topo, centralizado), pra tirar legenda/logo embutido na fonte (licao 20)
    # "topo": pixels pra pular no alto da fonte antes do recorte (faixa branca embutida, licao 34)
    rec = tr.get("recorte")
    topo = tr.get("topo", 0)
    crop = f"crop=iw*{rec}:ih*{rec}:(iw-iw*{rec})/2:{topo}," if rec else ""
    if tr.get("delogo"):  # "x:y:w:h" (ou lista deles) na fonte 1080p: apaga marca d'agua do canal de origem (licao 24)
        logos = tr["delogo"] if isinstance(tr["delogo"], list) else [tr["delogo"]]
        for lg in reversed(logos):
            x, y, w_, h_ = lg.split(":")
            crop = f"delogo=x={x}:y={y}:w={w_}:h={h_}," + crop
    vf = (f"fps=30,{crop}scale=2880:-2:flags=bicubic,"
          f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30,"
          f"format=yuv420p,{tr.get('cor', COR)},noise=alls=6:allf=t")  # "cor" por trecho: cena de serie mais clara (licao 25)
    if not os.path.exists(out):
        src = os.path.join(FONTES, tr["fonte"] + ".mp4")
        af = "highpass=f=70,loudnorm=I=-16:TP=-1.5:LRA=9,aresample=48000," + afade.rstrip(",")
        entradas = ["-ss", f"{ini:.3f}", "-t", f"{dur:.3f}", "-i", src]
        filtro = ["-vf", vf, "-af", af]
        cob = tr.get("cobrir")  # {"de", "ate", "com"}: tampa a imagem de "de" a "ate" com outro momento da fonte ("com"), audio intacto
        if cob:
            a0, a1 = max(cob["de"], ini) - ini, min(cob["ate"], fim) - ini
            entradas += ["-ss", f"{cob['com']:.3f}", "-t", f"{a1 - a0:.3f}", "-i", src]
            filtro = ["-filter_complex",
                      f"[1:v]setpts=PTS-STARTPTS+{a0:.3f}/TB[c];[0:v][c]overlay=eof_action=pass:"
                      f"enable='between(t,{a0:.3f},{a1:.3f})'[m];[m]{vf}[v];[0:a]{af}[a]",
                      "-map", "[v]", "-map", "[a]"]
        run(["ffmpeg", "-y", "-v", "error", *entradas, *filtro,
             *ENC_SEG, "-c:a", "aac", "-b:a", "192k",
             "-ar", "48000", "-ac", "2", out + ".tmp.mp4"])
        os.replace(out + ".tmp.mp4", out)
    # legenda: tempo da palavra no trecho + inicio do trecho no video final
    off = t_global - ini
    blocos = blocos_legenda(ws)
    sem_leg = tr.get("sem_legenda", [])  # [[ini, fim]] na fonte: cartela de texto propria da fonte (licao 21)
    for j, b in enumerate(blocos):
        if any(x0 <= b[0][0] <= x1 for x0, x1 in sem_leg):
            continue
        a = b[0][0] + off
        z = (blocos[j + 1][0][0] + off) if j + 1 < len(blocos) else b[-1][1] + off + 0.3
        z = min(z, b[-1][1] + off + 0.6)
        eventos.append((a, z, texto_bloco(b)))
    clips.append((out, dur))
    print(f"trecho {i+1}: {tr['fonte']} {ini:.1f}-{fim:.1f} ({dur:.1f}s) -> {t_global:.1f}s", flush=True)
    t_global += dur - XF

total = t_global + XF

# Com folgas curtas, o fim de um trecho encosta no comeco do seguinte: legenda nao pode sobrepor
eventos.sort()
for k in range(len(eventos) - 1):
    a, z, txt = eventos[k]
    eventos[k] = (a, min(z, eventos[k + 1][0] - 0.02), txt)

# Arquivo de legenda ASS
ass = os.path.join(BUILD, "legenda.ass")
with open(ass, "w", encoding="utf-8") as f:
    f.write("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding\n"
            "Style: Fala,Georgia,80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,1,0,1,1.5,3,5,80,80,0,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    for a, z, txt in eventos:
        if txt:
            f.write(f"Dialogue: 0,{ass_tempo(a)},{ass_tempo(z)},Fala,,0,0,0,,{{\\pos(960,700)\\fad(90,60)}}{txt}\n")

# Junta os trechos com dissolve (video) e crossfade (audio)
cmd = ["ffmpeg", "-y", "-v", "error"]
for c, _ in clips:
    cmd += ["-i", c]
musica = os.path.join(PASTA, "musica", "musica.mp3")
cmd += ["-i", musica]
fc, v, a, acc = [], "[0:v]", "[0:a]", 0.0
for i in range(1, len(clips)):
    acc += clips[i - 1][1] - XF
    fc.append(f"{v}[{i}:v]xfade=transition=fade:duration={XF}:offset={acc:.3f}[v{i}]")
    fc.append(f"{a}[{i}:a]acrossfade=d={XF}:c1=tri:c2=tri[a{i}]")
    v, a = f"[v{i}]", f"[a{i}]"
m = len(clips)
# Musica: entra suave, sai suave, abaixa quando tem fala (ducking leve)
# Nos intervalos a musica sobe rapido (release curto) pra nao ficar buraco de som
fc.append(f"[{m}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,volume=0.42,"
          f"afade=t=in:d=2,afade=t=out:st={max(0, total-4):.3f}:d=4[mus]")
fc.append(f"{a}asplit=2[voz][sc]")
fc.append("[mus][sc]sidechaincompress=threshold=0.04:ratio=4:attack=120:release=350[musd]")
fc.append("[voz][musd]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[aout]")
fc.append(f"{v}subtitles=legenda.ass:fontsdir=C\\\\:/Windows/Fonts[vout]")
final = os.path.join(PASTA, "teste-15s.mp4" if TESTE else "video-final.mp4")
cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
        *ENC_FINAL, "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final]
r = subprocess.run(cmd, cwd=BUILD, creationflags=0x4000, capture_output=True, text=True, encoding="utf-8", errors="replace")
if r.returncode != 0:
    print(r.stderr[-3000:]); raise SystemExit("render final falhou")
print(f"pronto: {final} ({total/60:.2f} min)")
