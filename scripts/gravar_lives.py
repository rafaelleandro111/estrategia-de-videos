"""
Grava as lives dos streamers ao mesmo tempo, sozinho.

Vigia cada canal. Quando entra ao vivo, grava. Quando a live acaba, para,
converte pra .mp4 e volta a vigiar. Cada streamer roda separado (uma live
não trava a outra). Impede o PC de suspender enquanto roda.

Uso:
  python scripts/gravar_lives.py                    # melhor qualidade (1080p60), roda até fechar (Ctrl+C)
  python scripts/gravar_lives.py --qualidade 720p   # só se o disco apertar
  python scripts/gravar_lives.py --teste 5          # grava só 5 min de quem estiver ao vivo e sai
  python scripts/gravar_lives.py --so coringa       # só um streamer
  python scripts/gravar_lives.py --so paulinho --youtube   # grava direto pelo YouTube (pula a Kick)
  (Paulinho: tenta a Kick; se a live cair ou der erro, grava pelo YouTube sozinho)
  python scripts/gravar_lives.py --canal gaules=https://kick.com/gaules   # qualquer canal
  python scripts/gravar_lives.py --pasta D:/lives/paulinho --canal "live paulinho 2=<url>"   # outra pasta

Saída: D:/lives/<streamer>/<streamer>_AAAA-MM-DD_HH-MM.mp4
Log:   D:/lives/gravar_lives.log
"""
import argparse
import ctypes
import datetime as dt
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

# Ordem = preferência. Se o primeiro falhar (live caindo, erro), grava pelo próximo.
STREAMERS = {
    "coringa": ["https://kick.com/coringa"],
    "paulinho": ["https://kick.com/paulinholokobr", "https://www.youtube.com/@PaulinhoLOKOoficial/live"],
    "yuri22": ["https://www.youtube.com/@yuri22ofc/live"],
}
PAUSA_SE_FALHAR = 300       # segundos que um link com erro fica de lado antes de tentar de novo

PASTA = Path("D:/lives")
CHECAR_A_CADA = 60          # segundos entre checagens quando o canal está offline
ESPACO_MINIMO_GB = 20       # para de gravar se o D: ficar abaixo disso

QUALIDADES = {
    "melhor": "best",
    "720p": "720p60,720p,best",
    "1080p": "1080p60,1080p,best",
    "480p": "480p30,480p,best",
}

parar = threading.Event()
log_lock = threading.Lock()


def achar(exe, padrao):
    caminho = shutil.which(exe)
    if caminho:
        return caminho
    if Path(padrao).exists():
        return padrao
    sys.exit(f"Não achei o {exe}. Instale antes de rodar.")


STREAMLINK = achar("streamlink", r"C:\Users\Administrator\AppData\Local\Programs\Streamlink\bin\streamlink.exe")
FFMPEG = achar("ffmpeg", "ffmpeg")


def log(nome, msg):
    linha = f"[{dt.datetime.now():%d/%m %H:%M:%S}] [{nome}] {msg}"
    with log_lock:
        print(linha, flush=True)
        try:
            with open(PASTA / "gravar_lives.log", "a", encoding="utf-8") as f:
                f.write(linha + "\n")
        except OSError:
            pass


def espaco_livre_gb():
    return shutil.disk_usage(PASTA).free / 1024**3


def sem_suspender(ligar=True):
    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED: PC não dorme enquanto o script roda
    try:
        flags = 0x80000000 | (0x00000001 if ligar else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass


def esta_ao_vivo(url):
    r = subprocess.run([STREAMLINK, "--json", url], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=90)
    return '"streams"' in r.stdout and '"error"' not in r.stdout


def para_mp4(ts, nome):
    mp4 = ts.with_suffix(".mp4")
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(ts), "-c", "copy",
                        "-movflags", "+faststart", str(mp4)], capture_output=True, text=True)
    if r.returncode == 0 and mp4.exists() and mp4.stat().st_size > 0:
        ts.unlink()
        log(nome, f"pronto: {mp4} ({mp4.stat().st_size / 1024**3:.1f} GB)")
    else:
        log(nome, f"ERRO ao converter, mantive o .ts: {ts} | {r.stderr.strip()[:200]}")


def achar_link_ao_vivo(nome, urls, falhou):
    """Primeiro link (na ordem) que está ao vivo e não falhou há pouco."""
    agora = time.time()
    for url in urls:
        if agora - falhou.get(url, 0) < PAUSA_SE_FALHAR:
            continue
        if esta_ao_vivo(url):
            return url
    return None


def gravar(nome, urls, qualidade, minutos_teste):
    pasta = PASTA / nome
    pasta.mkdir(parents=True, exist_ok=True)
    falhou = {}
    log(nome, f"vigiando {' | reserva: '.join(urls)}")
    while not parar.is_set():
        try:
            if espaco_livre_gb() < ESPACO_MINIMO_GB:
                log(nome, f"D: com menos de {ESPACO_MINIMO_GB} GB livres. Não vou gravar até liberar espaço.")
                parar.wait(600)
                continue
            url = achar_link_ao_vivo(nome, urls, falhou)
            if not url:
                if minutos_teste:
                    log(nome, "offline, fora do teste")
                    return
                parar.wait(CHECAR_A_CADA)
                continue

            arquivo = pasta / f"{nome}_{dt.datetime.now():%Y-%m-%d_%H-%M}.ts"
            cmd = [STREAMLINK, url, qualidade, "-o", str(arquivo),
                   "--hls-live-restart", "--stream-segment-threads", "3",
                   "--stream-timeout", "120", "--retry-open", "5", "--loglevel", "warning"]
            if minutos_teste:
                horas, minutos = divmod(minutos_teste, 60)
                cmd += ["--stream-segmented-duration", f"{horas:02d}:{minutos:02d}:00"]
            log(nome, f"AO VIVO, gravando em {arquivo.name} ({url})")
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace")
            while proc.poll() is None:
                if parar.wait(5):
                    proc.terminate()
                    proc.wait(30)
            erro = (proc.stderr.read() or "").strip()
            if erro:
                log(nome, f"streamlink: {erro[-300:]}")
            if arquivo.exists() and arquivo.stat().st_size > 1024 * 1024:
                log(nome, "live acabou, convertendo pra .mp4")
                para_mp4(arquivo, nome)
            else:
                if arquivo.exists():
                    arquivo.unlink()
                if len(urls) > 1:
                    falhou[url] = time.time()
                    log(nome, "não gravou nada por esse link, vou tentar o reserva")
            if minutos_teste:
                return
            parar.wait(15)  # queda rápida: volta a checar logo
        except Exception as e:
            log(nome, f"erro: {e}. Tento de novo em 1 min.")
            parar.wait(60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qualidade", choices=QUALIDADES, default="melhor")
    ap.add_argument("--teste", type=int, metavar="MIN", help="grava só MIN minutos e sai")
    ap.add_argument("--so", nargs="+", choices=STREAMERS, help="gravar só esses streamers")
    ap.add_argument("--canal", nargs="+", metavar="NOME=URL",
                    help="gravar qualquer canal (Kick, Twitch, YouTube) no lugar da lista fixa. "
                         "Reserva: NOME=URL1,URL2")
    ap.add_argument("--pasta", help="pasta base no lugar de D:/lives (cada canal vira uma subpasta)")
    ap.add_argument("--youtube", action="store_true",
                    help="gravar direto pelo YouTube (pula a Kick) de quem tem link do YouTube")
    a = ap.parse_args()
    global PASTA
    if a.pasta:
        PASTA = Path(a.pasta)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    PASTA.mkdir(parents=True, exist_ok=True)
    if a.canal:
        escolhidos = {n: u.split(",") for n, u in (c.split("=", 1) for c in a.canal)}
    else:
        escolhidos = {n: u for n, u in STREAMERS.items() if not a.so or n in a.so}
    if a.youtube:
        escolhidos = {n: [u for u in us if "youtube.com" in u] or us for n, us in escolhidos.items()}
    log("geral", f"início | {a.qualidade} | {', '.join(escolhidos)} | livre no D: {espaco_livre_gb():.0f} GB")
    sem_suspender(True)

    threads = [threading.Thread(target=gravar, args=(n, u, QUALIDADES[a.qualidade], a.teste), daemon=True)
               for n, u in escolhidos.items()]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(1)
    except KeyboardInterrupt:
        log("geral", "parando (Ctrl+C), fechando as gravações...")
        parar.set()
        for t in threads:
            t.join(120)
    finally:
        sem_suspender(False)
        log("geral", "fim")


if __name__ == "__main__":
    main()
