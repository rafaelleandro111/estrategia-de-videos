---
format: 1920x1080
duration: template (peças de 2-6 s + corpo de duração variável)
message: "Uma IA tentando criar algo de verdade, nível por nível, e você descobre se ela consegue"
arc: Abertura → [Nível N → Gravação do agente → Veredito] x3 → Placar final
audience: público BR curioso por IA (jovem/gamer e iniciantes em criar com IA)
mode: collaborative
---

## Decisões

- **Formato:** 1920x1080 (longo) + 1080x1920 (cortes). Narração Kokoro pm_santa, sem música por padrão (variável `musica` opcional). Legendas sempre ligadas; conteúdo fica nos 83% de cima.
- **Espinha:** uma janela de terminal persistente. Tudo acontece dentro dela: o título é digitado como comando, os níveis são comandos, a gravação aparece dentro da janela, o veredito é a saída do comando.
- **Paleta:** fundo `#0A0F0B` (preto puxado pro verde, não #000), texto `#D8F3DC`, destaque `#39FF14` (verde neon, escolha do dono), erro `#FF3B3B` (só no veredito "DEU ERRADO"), cinza de interface `#5C6B60`.
- **Tipografia:** JetBrains Mono 400/700 (terminal, legendas, rótulos) + Archivo Black (palavras de impacto: NÍVEL, nome do desafio, veredito). Ambas embutidas no renderer.
- **Proibido:** gradiente linear de tela cheia, brilho exagerado, UI falsa da IA (a gravação é sempre real), emoji na tela, slideshow (cada peça nasce da janela do terminal, não de um card novo).
- **Quadro parado:** o veredito segura 1 s parado depois do carimbo, pro resultado assentar.

## Frame 1 — Abertura

- scene: Terminal abre, digita o título do vídeo como comando, cursor pisca
- duration: 5s
- transition_in: cut
- status: built
- src: compositions/abertura.html
- voiceover: gancho do roteiro (variável)
- variaveis: titulo, ia, subtitulo

Janela do terminal ocupa a tela. Linha 1 `> agente --ia "GPT 6 Astra"`; o título ("ELE CONSEGUE CRIAR UM JOGO 3D?") digita letra a letra em Archivo Black grande. Por quê: entrega a promessa do vídeo no primeiro segundo.

## Frame 2 — Cartela de nível

- scene: "> NÍVEL 2_" com nome do desafio e barra de dificuldade
- duration: 3s
- transition_in: wipe (linha de varredura do terminal, de cima pra baixo)
- status: built
- src: compositions/cartela-nivel.html
- variaveis: numero, desafio, dificuldade (1-5)

Por quê: cada nível é uma pergunta nova pro espectador, e a cartela marca a virada.

## Frame 3 — Agente trabalhando (corpo)

- scene: Gravação de tela real dentro da janela do terminal, barra de status no topo, legenda embaixo
- duration: variável (vem do video.json)
- transition_in: cut
- status: built
- src: compositions/tela-agente.html
- variaveis: gravacao, ia, nivel, cronometro_inicio

Barra superior: `● GPT 6 Astra · nível 2 · 06:12` (cronômetro corre). Gravação ocupa ~85% da largura. Legenda em JetBrains Mono, palavra falada em verde. Zoom: punch-in suave numa região (x, y, escala) definida por trecho no video.json. Por quê: é a prova real, o coração do vídeo.

## Frame 4 — Veredito

- scene: Carimbo "✓ FUNCIONOU" (verde) ou "✗ DEU ERRADO" (vermelho) + tempo gasto
- duration: 2.5s
- transition_in: cut
- status: built
- src: compositions/veredito.html
- variaveis: resultado (ok/erro), tempo, comentario

Saída de comando: `exit 0` / `exit 1`. Segura 1 s parado. Por quê: mostrar o erro é o que dá credibilidade aos acertos.

## Frame 5 — Placar final

- scene: Os 3 níveis listados com ✓/✗ e pergunta pro próximo vídeo
- duration: 6s
- transition_in: wipe
- status: built
- src: compositions/placar.html
- variaveis: niveis (lista), pergunta_cta

Por quê: fecha a escada e puxa comentário ("qual IA eu testo agora?").

## Frame 6 — Corte vertical 9:16

- scene: Título do corte no topo, gravação no meio (recorte da região de interesse), legenda grande embaixo
- duration: variável (15-60 s)
- transition_in: cut
- status: built
- src: compositions/corte-vertical.html
- variaveis: titulo_corte, gravacao, recorte (x, y, largura), ia

Renderizado direto em 1080x1920. Por quê: cada corte puxa audiência pro vídeo longo.
