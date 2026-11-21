# Short/TikTok de GTA (camera em cima, faixa com titulo no meio, jogo embaixo, legenda palavra por palavra).
# Uso: python -I scripts/gta/short_gta.py <job.json> [--previa]
# job.json:
# {
#   "pasta": "marketing/youtube/2026-11-19-shorts-descobertas",
#   "nome": "bistecone-pe-grande",
#   "titulo": "BISTECONE ACHA O PÉ GRANDE|E SAI CORRENDO",       (| separa as 2 linhas)
#   "fonte": "kick:<master.m3u8 do VOD>"  ou  "youtube:<id do VOD>",
#   "pedacos": [["4:10:00", "4:12:05"]],                           (tempos no VOD; varios = cortes secos)
#   "cam": [x, y, w, h],                                           (caixa da webcam na fonte; ideal w/h ~ 1.45)
#   "jogo_x": 452                                                  (opcional; esquerda do recorte 1016 px em 1080p)
# }
# Saida: <pasta>/<nome>.mp4 (faixa azul, YouTube canal principal) e <pasta>/<nome>-tiktok.mp4 (faixa rosa Vice City)
import json, pathlib, subprocess, sys
from statistics import mean

RAIZ = pathlib.Path(__file__).resolve().parents[2]
job = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
PREVIA = '--previa' in sys.argv
pasta = RAIZ / job['pasta']; work = pasta / 'build' / job['nome']; work.mkdir(parents=True, exist_ok=True)
fontes = pasta / 'fontes'; fontes.mkdir(exist_ok=True)


def seg(t):
    p = [float(x) for x in str(t).split(':')]
    return sum(v * 60 ** i for i, v in enumerate(reversed(p)))


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', **kw)
    if r.returncode:
        print(r.stderr[-1500:]); raise SystemExit('falhou: ' + ' '.join(map(str, cmd[:4])))
    return r.stdout


# 1) baixar os pedacos
tipo, ref = job['fonte'].split(':', 1)
pecas = []
for i, (a, b) in enumerate(job['pedacos']):
    a, b = seg(a), seg(b)
    out = fontes / f"{job['nome']}-p{i}.mp4"
    if not out.exists():
        if tipo == 'kick':
            url = ref.rsplit('/', 1)[0] + '/1080p60/playlist.m3u8'
            run(['ffmpeg', '-v', 'error', '-y', '-ss', str(a), '-i', url, '-t', str(b - a), '-c', 'copy', str(out)])
        else:
            run(['yt-dlp', '-q', '--no-warnings', '-f', '623+140/308+140/299+140', '--download-sections', f'*{a}-{b}',
                 '--merge-output-format', 'mp4', '-o', str(out), f'https://www.youtube.com/watch?v={ref}'])
    pecas.append(out)

# 2) juntar (corte seco com fade curto de audio)
fonte = fontes / f"{job['nome']}.mp4"
if not fonte.exists():
    ins, fc = [], ''
    for i, p in enumerate(pecas):
        ins += ['-i', str(p)]
        fc += f'[{i}:v]setpts=PTS-STARTPTS[v{i}];[{i}:a]asetpts=PTS-STARTPTS,afade=t=in:d=0.08[a{i}];'
    fc += ''.join(f'[v{i}][a{i}]' for i in range(len(pecas))) + f'concat=n={len(pecas)}:v=1:a=1[v][a]'
    run(['ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', fc, '-map', '[v]', '-map', '[a]',
         '-c:v', 'libx264', '-preset', 'fast', '-crf', '14', '-r', '60', '-c:a', 'aac', '-b:a', '192k', str(fonte)])
W, H = map(int, run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                     '-of', 'csv=p=0', str(fonte)]).strip().split(','))
dur = float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(fonte)]))
k = H / 1080

# 3) palavras (Whisper)
wfile = work / 'words.jsonl'
if not wfile.exists():
    import numpy as np
    from faster_whisper import WhisperModel
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(fonte), '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                         capture_output=True).stdout
    audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    m = WhisperModel('medium', device='cpu', compute_type='int8', cpu_threads=6)
    segs, _ = m.transcribe(audio, language='pt', beam_size=5, word_timestamps=True, vad_filter=True)
    with wfile.open('w', encoding='utf-8') as f:
        for s in segs:
            f.write(json.dumps([s.start, s.end, s.text, [[w.start, w.end, w.word, w.probability] for w in s.words]],
                               ensure_ascii=False) + '\n')
transcript = [json.loads(l) for l in wfile.read_text(encoding='utf-8').splitlines()]

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Impact,76,&H00FFFFFF,&H00FFFFFF,&H00090708,&H00000000,-1,0,0,0,100,100,1,0,1,7,2,5,0,0,0,1
Style: Caption,Arial,55,&H00FFFFFF,&H0000E7FF,&H00161616,&H40000000,-1,0,0,0,100,100,0,0,1,4,1,5,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ass_time(s):
    cs = round(s * 100)
    return f'{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}'


def make_ass(fill, borda, end):
    ev = []
    def event(a, b, style, val):
        a, b = max(0, a), min(end, b)
        if round(a * 100) < round(b * 100):
            ev.append(f'Dialogue: 0,{ass_time(a)},{ass_time(b)},{style},,0,0,0,,{val}')
    l1, l2 = job['titulo'].split('|')
    def plate(delay, x, y, w):
        x = round(x)
        tags = rf'\an7\move({x + 32},{y},{x},{y},0,250)\fad(135,0)\c{fill}\3c{borda}\bord5\shad0\p1'
        event(delay, end, 'Title', '{' + tags + '}' + f'm 26 0 l {w} 0 {w - 26} 58 0 58' + r'{\p0}')
    w1 = min(900, max(480, len(l1) * 30 + 95)); w2 = min(900, max(430, len(l2) * 32 + 95))
    plate(.02, (1080 - w1) / 2, 595, w1); plate(.13, (1080 - w2) / 2, 658, w2)
    event(.02, end, 'Title', r'{\move(572,625,540,625,0,250)\fad(135,0)\fs57\i1\bord0\shad0}' + l1)
    event(.13, end, 'Title', r'{\move(572,688,540,688,0,250)\fad(135,0)\fs60\i1\bord0\shad0}' + l2)
    for s0, s1, text, words in transcript:
        if len(text.strip()) <= 2 or not words or mean(w[3] for w in words) < .45:
            continue
        groups, g = [], []
        for a, b, w, p in words:
            w = w.replace('{', '').replace('}', '').replace('\\', '').strip()
            if not w:
                continue
            if g and (len(g) >= 4 or len(w) + sum(len(x[2]) + 1 for x in g) > 25 or a - g[-1][1] > .42):
                groups.append(g); g = []
            g.append((a, b, w, p))
        if g:
            groups.append(g)
        for g in groups:
            for n, (a, b, _, _) in enumerate(g):
                b = min(g[n + 1][0], max(b, a + .12)) if n + 1 < len(g) else b + .10
                txt = ' '.join(r'{\c&H00E7FF&}' + x[2] + r'{\r}' if i == n else x[2] for i, x in enumerate(g))
                event(a, b, 'Caption', r'{\pos(485,1370)}' + txt)
    (work / 'corte.ass').write_text(HEADER + '\n'.join(ev) + '\n', encoding='utf-8-sig')


cx, cy, cw, ch = job['cam']
gw = round(1016 * k); gx = round(job['jogo_x'] * k) if 'jogo_x' in job else round((W - gw) / 2)
VERSOES = [('', 'faixa-azul.png', '&H3A1408&', '&HFF963C&'), ('-tiktok', 'faixa-vice-city.png', '&H22121E&', '&HAC04F6&')]
for suf, faixa, fill, borda in VERSOES:
    src = RAIZ / 'identidade' / 'shorts' / faixa
    (work / faixa).write_bytes(src.read_bytes())
    end = 6 if PREVIA else dur
    make_ass(fill, borda, end)
    graph = (
        '[0:v]split[portrait][game];'
        f'[portrait]crop={cw}:{ch}:{cx}:{cy},split[cs][cb];'
        '[cs]scale=798:552:flags=lanczos,unsharp=5:5:0.22:5:5:0,setsar=1[cam];'
        '[cb]scale=1080:748:flags=bilinear,crop=1080:552:0:98,gblur=sigma=14:steps=2,eq=brightness=-0.09:saturation=0.72,setsar=1[cf];'
        '[cf][cam]overlay=x=141:y=0[face];'
        f'[game]crop={gw}:{H}:{gx}:0,scale=1080:1148:flags=lanczos,unsharp=5:5:0.30:5:5:0,eq=gamma=1.06,setsar=1[play];'
        f'movie={faixa},scale=1080:220:flags=lanczos,format=yuv420p,setsar=1,loop=loop=-1:size=1:start=0,settb=1/60,setpts=N[band];'
        '[face][band][play]vstack=inputs=3:shortest=1,fps=60,ass=corte.ass')
    (work / 'corte.ffgraph').write_text(graph, encoding='ascii')
    if PREVIA:
        alvo = pasta / f"previa-{job['nome']}{suf}.jpg"
        cmd = ['ffmpeg', '-v', 'error', '-y', '-t', '1.2', '-i', str(fonte), '-/filter_complex', 'corte.ffgraph',
               '-update', '1', '-q:v', '2', str(alvo)]
    else:
        alvo = pasta / f"{job['nome']}{suf}.mp4"
        cmd = ['ffmpeg', '-v', 'error', '-y', '-i', str(fonte), '-/filter_complex', 'corte.ffgraph', '-map', '0:a',
               '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', '-c:a', 'aac', '-b:a', '192k',
               '-movflags', '+faststart', str(alvo)]
    run(cmd, cwd=work)
    print('ok', alvo)
    if PREVIA:
        break
print(f'duracao {dur:.1f}s')
