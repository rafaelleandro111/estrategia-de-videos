# Baixa a legenda automatica (pt) de um VOD da Kick e grava linha do tempo "H:MM:SS texto".
# Uso: python -I scripts/kick_legenda.py <master.m3u8 do VOD> <saida.txt>
import sys, re, urllib.request
from concurrent.futures import ThreadPoolExecutor
src, out = sys.argv[1], sys.argv[2]
base = src.rsplit('/', 1)[0] + '/subtitles/pt/'
H = {'User-Agent': 'Mozilla/5.0'}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30).read().decode('utf-8', 'replace')
pl = get(base + 'playlist.m3u8').splitlines()
segs, t = [], 0.0
for l in pl:
    if l.startswith('#EXTINF:'): dur = float(l[8:].split(',')[0])
    elif l.endswith('.vtt'): segs.append((t, l)); t += dur
def baixa(s):
    t0, nome = s
    try: txt = get(base + nome)
    except Exception: return []
    res = []
    for m in re.finditer(r'(\d+):(\d+):(\d+)\.\d+ --> [^\n]*\n(.+?)(?:\n\n|\Z)', txt, re.S):
        res.append((int(m[1])*3600+int(m[2])*60+int(m[3]), ' '.join(m[4].split())))
    if res and res[0][0] < t0 - 30:  # tempos relativos ao segmento
        res = [(t0 + a, b) for a, b in res]
    return res
with ThreadPoolExecutor(16) as ex: partes = list(ex.map(baixa, segs))
linhas, ult = [], ''
for p in partes:
    for a, b in p:
        if b == ult or (ult and b.startswith(ult)) or (ult and ult.endswith(b)): ult = b if len(b) > len(ult) else ult; continue
        linhas.append(f'{int(a)//3600}:{int(a)%3600//60:02}:{int(a)%60:02} {b}'); ult = b
open(out, 'w', encoding='utf-8').write('\n'.join(linhas))
print(out, len(linhas), 'linhas')
