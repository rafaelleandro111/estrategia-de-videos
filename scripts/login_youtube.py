# Login do YouTube pro AgentTube: abre o navegador, recebe o código em 127.0.0.1:8080 e grava o token em config/
# Uso: python -I scripts/login_youtube.py [arquivo]   (padrão tokens.json = canal principal; tokens-segundo.json = segundo canal)
import http.server, json, shutil, sys, time, urllib.parse, urllib.request, webbrowser

ARQ = sys.argv[1] if len(sys.argv) > 1 else "tokens.json"

CFG = "ferramentas/youtube-automation-agent/config"
REDIR = "http://127.0.0.1:8080/auth/callback"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/yt-analytics.readonly",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
cred = json.load(open(f"{CFG}/credentials.json", encoding="utf-8"))["youtube"]
url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id": cred["client_id"], "redirect_uri": REDIR, "response_type": "code",
    "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent select_account"})
codigo = {}


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        codigo["code"] = q.get("code", [None])[0]
        codigo["erro"] = q.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = "Pronto! Pode fechar esta aba e voltar pro Claude." if codigo["code"] else f"Erro: {codigo['erro']}"
        self.wfile.write(f"<h1 style='font-family:sans-serif;text-align:center;margin-top:80px'>{msg}</h1>".encode())

    def log_message(self, *a):
        pass


srv = http.server.HTTPServer(("127.0.0.1", 8080), H)
srv.timeout = 600
webbrowser.open(url)
print("navegador aberto, esperando autorização...", flush=True)
srv.handle_request()
if not codigo.get("code"):
    raise SystemExit(f"sem código: {codigo.get('erro')}")
dados = urllib.parse.urlencode({"code": codigo["code"], "client_id": cred["client_id"],
                                "client_secret": cred["client_secret"], "redirect_uri": REDIR,
                                "grant_type": "authorization_code"}).encode()
tok = json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", dados))
tok["expiry_date"] = int((time.time() + tok.get("expires_in", 3600)) * 1000)
import os
if os.path.exists(f"{CFG}/{ARQ}"): shutil.copy(f"{CFG}/{ARQ}", f"{CFG}/{ARQ}.bak")
json.dump({"youtube": tok}, open(f"{CFG}/{ARQ}", "w", encoding="utf-8"), indent=2)
print(f"LOGIN OK ({ARQ}) | refresh_token:", "sim" if tok.get("refresh_token") else "NAO",
      "| expira em teste:", "sim" if "refresh_token_expires_in" in tok else "nao")
