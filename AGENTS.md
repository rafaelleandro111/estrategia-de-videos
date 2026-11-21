# AGENTS.md — Estratégia de vídeos (contexto pro Codex)

Este arquivo explica o projeto pra qualquer agente de IA (Codex e similares).
O `CLAUDE.md` tem as mesmas regras pro Claude Code. Se algo conflitar, vale este arquivo quando o agente for o Codex.

## O que é

Sistema de trabalho pra operar um **canal no YouTube** (e TikTok) com produção o mais automatizada possível:
achar os melhores momentos, cortar, editar, fazer título e thumb, e publicar.
Formato pensado pra **cortes de lives** (episódios longos + Shorts 9:16), mas serve pra qualquer formato no YouTube.

## Primeiro uso: instalar

Se `_memoria/empresa.md` ainda estiver em branco, ou o usuário disser "instalar", "/instalar" ou "primeiro setup":
ler `.agents/skills/instalar/SKILL.md` e seguir. Ele entrevista o dono e preenche:

- `_memoria/empresa.md` — quem é, o que faz, o canal
- `_memoria/preferencias.md` — tom de voz, estilo, o que evitar
- `_memoria/estrategia.md` — foco atual, prioridades, prazos
- `identidade/design-guide.md` — cores, fontes, padrão de thumb

## Antes de qualquer tarefa, ler

1. Os 3 arquivos de `_memoria/` (quando preenchidos)
2. `identidade/design-guide.md` — pra thumb, banner, qualquer coisa visual
3. `scripts/video-falas/LICOES.md` — **obrigatório antes de cortar ou montar vídeo** (erros já resolvidos, não repetir)

Não precisa listar o que leu. Só usar o contexto.

## Skills

Ficam em `.agents/skills/<nome>/SKILL.md` (cópia de `.claude/skills/`). São instruções em texto: se a tarefa bater com uma, ler o SKILL.md e seguir.
Se uma skill mudar em `.claude/skills/`, copiar de novo pra `.agents/skills/`.

Principais:
- `instalar` — primeiro setup. `abrir` — começa a sessão com resumo do contexto. `atualizar` — reconcilia a memória com o estado do projeto
- `outliers-tema` / `outliers-canal` — vídeos que estouraram num assunto ou num canal
- `analisar-canal` — números do canal (YouTube Analytics). `analisar-video` — analisa um vídeo (imagem + fala)
- `youtube` — estratégia, roteiro, ganchos, SEO, Shorts, RPM
- `hyperframes`, `general-video`, `embedded-captions` — edição e legendas
- `canvas-design`, `banner-design` — thumbs e banner

## Regras de comportamento

- **Não executar nem baixar nada sem o dono pedir.** Pergunta ≠ ordem pra executar
- Responder curto, direto, em português. Se o dono não entender, explicar passo a passo em linguagem simples
- Sugerir o caminho mais simples já provado
- Quando der erro novo em vídeo, anotar em `scripts/video-falas/LICOES.md` com a solução
- Quando o dono corrigir algo de valor duradouro, perguntar se quer salvar (em `_memoria/` ou neste arquivo)
- Ao terminar uma tarefa repetível sem skill, perguntar se vira skill
- Não travar o PC: processar uma live por vez, subprocessos com prioridade baixa

## Regras de conteúdo (monetização)

- Só clipar streamer que libera cortes. **Crédito + link do streamer na descrição de todo vídeo**, @ visível na tela
- **Sem música de rádio do jogo** (Content ID)
- **Edição própria em todo vídeo** (legenda palavra por palavra, zoom na reação). Clipe cru cai em "conteúdo reutilizado" e não monetiza
- Thumb com 3 a 5 palavras, padrão visual consistente
- Guardar provas da edição em `<pasta-do-video>/provas/` (pra recurso se a monetização for negada)

## Fluxo de produção

1. **Obter a live:** `python scripts/gravar_lives.py` (Streamlink, grava sozinho quem entrar ao vivo) ou trecho do VOD com yt-dlp (`--download-sections`)
2. **Transcrever** local (faster-whisper): `scripts/video-falas/transcrever.py`
3. **Roteiro:** escolher trechos e ordem → **o dono aprova** antes de montar
4. **Montar episódio:** `python -I scripts/gta/montar_gta.py <pasta-do-video> teste` → depois sem `teste`. Dados em `<pasta>/episodio.json` (aceita vários streamers: `fonte`, `cam`, `streamer` por trecho)
5. **Conferir:** blackdetect, silencedetect e frase cortada
6. **Shorts:** `scripts/gta/short_gta.py` ou `scripts/video-falas/corte_vertical.py` → `<pasta>/cortes/`
7. **Publicar/agendar:** `node scripts/publicar_youtube.js <pasta-do-video> [cortes/publicar-NN.json]` (dados em `publicar.json`). Segundo canal: `--canal segundo`
8. **Banner:** `node scripts/subir_banner.js [png] [--canal segundo]`

## Estrutura de pastas

- `_memoria/` — empresa, preferências, estratégia
- `identidade/` — cores, fontes, logo, banner
- `marketing/youtube/<AAAA-MM-DD>-<tema>/` — **uma pasta por vídeo** (trechos, título, descrição, thumb, `transcricoes/`, `cortes/`, `publicar.json`)
- `marketing/youtube/pesquisa/` — pesquisa de nicho e concorrência
- `saidas/` — análises e documentos pontuais
- `dados/` — arquivos pra analisar (exports do YouTube Studio)
- `scripts/` — utilitários (gravar, montar, cortar, publicar, login)
- `ferramentas/` — programas locais e logins (fora do Git)

## Ambiente

- Feito no Windows (PowerShell). Rodar scripts Python com `python -I`
- Precisa: Python 3.11+, Node.js, FFmpeg, yt-dlp, Streamlink, faster-whisper
- **Login do YouTube:** criar um projeto no Google Cloud com a YouTube Data API, colocar `credentials.json` em `ferramentas/youtube-automation-agent/config/` e rodar `python -I scripts/login_youtube.py` (gera `tokens.json`; segundo canal: `tokens-segundo.json`)
- **Nunca commitar** `.env`, `credentials.json`, `tokens*.json` nem nada de `ferramentas/` (já estão no `.gitignore`)
