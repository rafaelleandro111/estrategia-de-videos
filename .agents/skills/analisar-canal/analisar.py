"""Relatório do canal canal principal (@seucanal): dados públicos + YouTube Analytics.

Usa o login do AgentTube (config/credentials.json + tokens.json). Nunca imprime chaves.
Uso: python -I analisar.py [--dias N]   (padrão: desde a criação do canal)
"""
import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

AGENT = "ferramentas/youtube-automation-agent/config"


def find(d, *keys):
    if isinstance(d, dict):
        for k in keys:
            if d.get(k):
                return d[k]
        for v in d.values():
            r = find(v, *keys)
            if r:
                return r


ap = argparse.ArgumentParser()
ap.add_argument("--dias", type=int)
ap.add_argument("--canal", default="principal", help="principal (padrão) ou segundo")
args = ap.parse_args()
TOKFILE = "tokens.json" if args.canal == "principal" else f"tokens-{args.canal}.json"


def token():
    cred = json.load(open(f"{AGENT}/credentials.json", encoding="utf-8"))
    tok = json.load(open(f"{AGENT}/{TOKFILE}", encoding="utf-8"))["youtube"]
    data = urllib.parse.urlencode({
        "client_id": find(cred, "client_id", "clientId"),
        "client_secret": find(cred, "client_secret", "clientSecret"),
        "refresh_token": tok["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    return json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data))["access_token"]


TOK = token()


def get(url, **p):
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(p),
                                 headers={"Authorization": "Bearer " + TOK})
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        return {"erro": json.loads(e.read()).get("error", {}).get("message", "")[:200]}


def api(path, **p):
    return get("https://www.googleapis.com/youtube/v3/" + path, **p)


def report(start, end, **p):
    d = get("https://youtubeanalytics.googleapis.com/v2/reports",
            ids="channel==MINE", startDate=start, endDate=end, **p)
    if "erro" in d:
        print("  (erro:", d["erro"], ")")
        return []
    return d.get("rows", [])


def dur(iso):
    # PT8M32S -> segundos
    n, s = "", 0
    for ch in iso[2:]:
        if ch.isdigit():
            n += ch
        else:
            s += int(n) * {"H": 3600, "M": 60, "S": 1}[ch]
            n = ""
    return s


ch = api("channels", part="snippet,statistics,contentDetails", mine="true")["items"][0]
st = ch["statistics"]
criado = ch["snippet"]["publishedAt"][:10]
hoje = dt.date.today().isoformat()
inicio = (dt.date.today() - dt.timedelta(days=args.dias)).isoformat() if args.dias else criado

print(f"# Canal {ch['snippet']['title']} — {hoje}")
print(f"Criado em {criado} | inscritos {st['subscriberCount']} | views {st['viewCount']} | vídeos {st['videoCount']}")

# Vídeos (inclui agendados/privados, porque o login é do dono)
uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
ids = [i["contentDetails"]["videoId"] for i in
       api("playlistItems", part="contentDetails", playlistId=uploads, maxResults=50).get("items", [])]
vids = api("videos", part="snippet,statistics,contentDetails,status", id=",".join(ids)).get("items", []) if ids else []
info = {}
print("\n## Vídeos (dados públicos, ao vivo)")
print("data | tipo | duração | status | views | likes | coment. | título")
for v in sorted(vids, key=lambda v: v["status"].get("publishAt") or v["snippet"]["publishedAt"]):
    s = dur(v["contentDetails"]["duration"])
    tipo = "Short" if "#shorts" in v["snippet"]["title"].lower() or s <= 60 else "Longo"
    status = v["status"]["privacyStatus"]
    quando = (v["status"].get("publishAt") or v["snippet"]["publishedAt"])[:10]
    if v["status"].get("publishAt") and status == "private":
        status = "agendado"
    if status == "public":
        info[v["id"]] = (v["snippet"]["title"], s)
    vs = v["statistics"]
    print(f"{quando} | {tipo} | {s // 60}:{s % 60:02d} | {status} | {vs.get('viewCount', 0)} | "
          f"{vs.get('likeCount', 0)} | {vs.get('commentCount', 0)} | {v['snippet']['title']}")

print(f"\n## Analytics de {inicio} a {hoje} (o YouTube atrasa ~2 dias)")

print("\n### Por vídeo: views | min assistidos | duração média (s) | % assistido | inscritos")
for r in report(inicio, hoje, dimensions="video", sort="-views", maxResults=50,
                metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained"):
    print(f"{info.get(r[0], (r[0],))[0]} | " + " | ".join(str(x) for x in r[1:]))

print("\n### Shorts x longos: views | duração média (s)")
for r in report(inicio, hoje, dimensions="creatorContentType", metrics="views,averageViewDuration", sort="-views"):
    print(" | ".join(str(x) for x in r))

print("\n### Por dia: views | min assistidos | inscritos")
for r in report(inicio, hoje, dimensions="day", sort="day",
                metrics="views,estimatedMinutesWatched,subscribersGained"):
    print(" | ".join(str(x) for x in r))

print("\n### Origem do tráfego")
for r in report(inicio, hoje, dimensions="insightTrafficSourceType", metrics="views", sort="-views"):
    print(" | ".join(str(x) for x in r))

print("\n### Aparelho")
for r in report(inicio, hoje, dimensions="deviceType", metrics="views", sort="-views"):
    print(" | ".join(str(x) for x in r))

print("\n### Termos de busca (YouTube)")
for r in report(inicio, hoje, dimensions="insightTrafficSourceDetail", metrics="views", sort="-views",
                filters="insightTrafficSourceType==YT_SEARCH", maxResults=15):
    print(" | ".join(str(x) for x in r))

print("\n### Retenção (% do público ainda assistindo em cada 10% do vídeo)")
for vid, (titulo, s) in info.items():
    rows = report(inicio, hoje, dimensions="elapsedVideoTimeRatio", metrics="audienceWatchRatio",
                  filters="video==" + vid)
    pts = [f"{int(r[0] * 100)}%:{r[1]:.2f}" for r in rows if round(r[0] * 100) % 10 == 0]
    print(f"{titulo}: " + (" ".join(pts) if pts else "sem dados (poucas views)"))

print("\nImpressões e CTR da thumb não saem por API: ver no Studio (aba Alcance).")
