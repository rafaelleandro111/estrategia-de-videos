---
name: analisar-canal
description: >
  Puxa os números reais do canal canal principal (@seucanal) (dados públicos + YouTube Analytics) e
  devolve um diagnóstico curto de como o canal está crescendo: views, tempo assistido,
  retenção, origem do tráfego, aparelho, termos de busca, Shorts x longos e agenda.
  Use quando o usuário disser "analisa o canal", "como tá o canal", "como tá crescendo",
  "números do canal", "/analisar-canal".
---

# /analisar-canal — Diagnóstico do canal

## Dependências

- **Estratégia:** `_memoria/estrategia.md` (meta de monetização, regra dos 30 vídeos, agenda)
- **Login:** o do AgentTube (`ferramentas/youtube-automation-agent/config/`), com escopo `yt-analytics.readonly`. A YouTube Analytics API já está ativada no projeto Google Cloud "Default Gemini Project" (desde 2026-10-20)

## Workflow

1. Rodar o relatório:
   ```
   python -I .claude/skills/analisar-canal/analisar.py            # desde a criação do canal
   python -I .claude/skills/analisar-canal/analisar.py --dias 28  # últimos 28 dias
   ```
2. Se o usuário tiver colocado um export do Studio em `dados/` (impressões, CTR), ler junto. Impressões e CTR **não saem pela API**
3. Responder com:
   - **Resumo de 1 linha:** está crescendo ou não, e se dá pra concluir algo
   - **Tabela** por vídeo (views, duração média, % assistido, inscritos)
   - **3 a 4 leituras** do que os números mostram
   - **Distância até a monetização:** 1.000 inscritos + 4.000 h (≈ views longas × duração média) ou 10 mi de views de Shorts em 90 dias
   - **2 a 3 ações**, coerentes com `estrategia.md`

## Como ler os números

- **O Analytics atrasa ~2 dias.** O número público (ao vivo) pode ser maior que o do Analytics. Vídeo publicado há menos de 2 dias ainda não entrou
- **Views do próprio dono:** muitas views no computador + duração de poucos segundos + origem "SUBSCRIBER" com 0 inscritos = o dono conferindo o vídeo. Não confundir com retenção ruim. **O dono também acha os próprios vídeos pela busca do YouTube**, então "Pesquisa do YouTube" (views e impressões) pode ser dele. Pra separar: olhar os termos de busca. Termo igual ao título = dono; termo genérico ("como vencer o medo") = gente de fora. Não afirmar nem um nem outro sem os termos
- **Impressões por origem** (Studio → Analytics → Alcance → Origem do tráfego) mostram se o problema é recomendação (0 em "Recursos de navegação"/"Vídeos sugeridos") ou clique (impressões altas, CTR baixo). A API não traz impressões: pedir o print ao dono
- **Retenção vazia** = poucas views, não é erro
- **Origem do tráfego:** `YT_SEARCH` = SEO funcionando; `SHORTS` = feed de Shorts; `RELATED_VIDEO`/`BROWSE` = o algoritmo começou a recomendar (é o sinal de crescimento de verdade)
- **Regra dos 30 vídeos:** antes disso, não propor mudar a fórmula (título, thumb, ordem emocional). Pode propor mudar agenda ou volume de Shorts
- Comparar sempre vídeos com o mesmo tempo no ar
- **Vídeo que falta na agenda:** abrir a pasta em `marketing/youtube/` antes de falar dele. Só está pronto se tiver o vídeo final e o `publicar.json`. Pasta só com `legendas/` = ainda em pesquisa, e aí a ação é produzir, não subir

## Erros conhecidos

- `The query is not supported` no relatório por vídeo → precisa de `maxResults` (já está no script)
- `has not been used in project ... or it is disabled` → ativar a YouTube Analytics API no Google Cloud do projeto que aparece no erro
- Token expirado/revogado (`invalid_grant`, HTTP 400 no token) → refazer o login do YouTube no AgentTube (`npm start`). Causa (2026-10-25): o app OAuth do "Default Gemini Project" estava em modo **Teste**, que derruba o login a cada 7 dias. Solução definitiva: Google Cloud → Tela de consentimento OAuth → **Publicar app**. Isso também trava o `publicar_youtube.js`. **Resolvido em 2026-10-27:** app publicado (precisou preencher em Branding a página inicial e a política de privacidade com o link do canal + domínio autorizado `youtube.com`). Pra refazer o login: `python -I scripts/login_youtube.py` (abre o navegador; o `oauth-server.js` do AgentTube não serve, o endereço de retorno não bate com a porta)
