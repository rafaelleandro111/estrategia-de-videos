# Vídeo de falas (formato So uma chance): passo a passo e lições

Ler antes de montar qualquer vídeo de falas. Cada lição veio de um erro real no vídeo "Faça Mesmo Com Medo." (2026-10-13).

## Passo a passo

1. **Escolher fontes:** `yt-dlp "ytsearch8:<palestrante> <tema>"` e conferir a resolução com `--print "%(height)s"`. Só 1080p ou mais, de preferência canal oficial
2. **Achar as falas pela legenda automática do YouTube**, não pelo Whisper: `yt-dlp --skip-download --write-auto-subs --sub-langs pt-orig` + `vtt2txt.py`. Leva segundos. Esperar 4s entre vídeos (senão dá erro 429)
3. **Aprovar a lista de trechos com o dono** antes de baixar e montar
4. **Baixar só as fontes aprovadas** em 1080p pra `<pasta-do-video>/fontes/`
5. **Transcrever com o Whisper só as janelas dos trechos** (`transcrever.py` + `janelas.json`), com folga de 15s depois da última frase
6. **Pontos de corte:** `pausas.py` e `gaps.py` mostram as frases e as pausas. Montar `trechos.json` (fonte, ini, fim, corrigir)
7. **Montar:** `python -I montar.py <pasta-do-video> <pasta-transcricoes> teste` (só o 1º trecho) → olhar os quadros → rodar sem `teste`
8. **Conferir antes de mostrar:** blackdetect, silencedetect e transcrever o vídeo final de novo pra ver se nenhuma frase foi cortada

## Erros que já aconteceram (não repetir)

1. **faster-whisper não abre MP4** (erro `metadata_errors` da biblioteca av). Solução: o `transcrever.py` extrai o áudio com o ffmpeg e passa como numpy
2. **Prioridade baixa não pegava:** o `python.exe` do Windows abre um subprocesso, e é ele que trabalha. Dentro do Python usar `creationflags=0x4000` (BELOW_NORMAL) nos subprocessos
3. **O tempo de palavra do Whisper atrasa até 0,4s e "estica" as palavras por cima das pausas.** Cortar pelo Whisper pega o começo da frase seguinte. Solução: o `montar.py` corta na **pausa real do áudio** (silencedetect), e o Whisper só localiza a frase
4. **Janela do Whisper curta demais** cortou a última palavra do Karnal ("resultados"). Sempre dar 15s de folga depois da última frase usada
5. **Zoom com `scale` + `eval=frame` faz o ffmpeg 9 travar** (código 3221225477 / 0xC0000005). Solução: `zoompan` com a imagem ampliada pra 2880 antes (fica suave e não trava)
6. **Arquivo pela metade era reaproveitado** depois de um travamento. Solução: o `montar.py` grava em `.tmp.mp4` e só renomeia quando termina
7. **Fade de áudio com início negativo** quando o trecho começa no segundo 0. Solução: limitar a 0
8. **Granulado forte (noise=10) deixou o vídeo com 4 GB e o render lento.** Usar noise=6
9. **A placa de vídeo (GTX 1660 Super) não foi usada:** o driver NVIDIA está abaixo da versão 610. O `montar.py` detecta sozinho e usa o NVENC quando o driver for atualizado
10. **Trechos que repetem a mesma ideia** (Clóvis e Karnal explicando "medo é imaginação" duas vezes). Na hora de escolher, cortar o repetido
11. **O Whisper erra palavras** ("mãe" no lugar de "mente", "ficamos" no lugar de "ficarmos"). Corrigir em `trechos.json` → `corrigir`
12. **As transcrições ficaram na pasta temporária e sumiram** (2026-10-14, ao aumentar o vídeo do medo pra 8 min). Solução: guardar em `<pasta-do-video>/transcricoes/`
13. **Transcrever de novo muda o tempo das palavras** e 4 trechos perderam a última palavra ("leviana", "estudando", "mornos"). Solução: depois de transcrever, rodar `bordas.py` e ajustar `ini`/`fim` até toda borda fechar em frase completa
14. **O Whisper pulou uma frase inteira** ("Você tem medo de avião?"). Conferir a legenda do YouTube (tem tempo por palavra) e inserir as palavras na transcrição
15. **Faixa de propaganda da fonte** ("Inscreva-se no podcast...", Cortella/Sophya) no meio de um trecho. Achar com `crop` + `signalstats` (SATAVG > 15 na faixa) e tampar com `"cobrir": {"de", "ate", "com"}` no `trechos.json` (troca a imagem por outro momento da mesma fonte, áudio intacto). Nessa fonte há faixa em 99–104s, 243–255s e 449–461s
16. **Inserir trecho no meio desloca os nomes `segNN.mp4`** e o `montar.py` reaproveitaria pedaços errados. Mover a pasta `build/` antes de remontar

## Padrão visual que funcionou

- Preto e branco: `hue=s=0, eq=contrast=1.32:brightness=-0.07:gamma=0.9, vignette=PI/3.6`
- Zoom lento alternado (entra/sai 6%) em cada trecho
- Dissolve de 0,8s entre trechos, 1s de folga antes e 1,2s depois de cada fala
- Legenda: Georgia negrito maiúscula 80, palavra-chave 132, blocos de até 3 palavras, no centro um pouco abaixo (y=700)
- Música: Scott Buckley CC-BY, volume 0,32 com ducking leve quando tem fala

## Lições do vídeo "Desistir" (2026-10-15)

17. **Buraco de som entre os trechos** (o dono notou no vídeo do medo): folga de 1,0s antes + 1,2s depois da fala, com dissolve de 0,8s, deixava ~1,4s sem voz, e a música demorava ~0,9s pra voltar. Solução no `montar.py`: folgas de 0,35s/0,55s, dissolve de 0,5s, música base 0,42 e ducking com release de 350ms
18. **Fala emendada sem pausa vaza a palavra seguinte** ("acomodação no fracasso. **Por isso**", Karnal): o corte procura a pausa real mais perto e, se o palestrante não pausa, passa do ponto. Solução: `"corte_fim": <segundo>` no `trechos.json` força o fim da fala (usar o fim da última palavra no Whisper)
19. **Vídeo abaixo de 8 min** (o Desistir saiu com 6:26): 8 min libera anúncio no meio do vídeo. Ao escolher os trechos, somar a duração e mirar 8:15 a 8:45. Pra completar, o mais fácil é esticar trechos já aprovados (o que o palestrante disse logo antes ou depois)
20. **Fonte com legenda embutida e logo** (Calabrez no canal Pra Frente): ficavam duas legendas na tela. Achar olhando um quadro de cada trecho no vídeo final. Solução: `"recorte": 0.7` no `trechos.json` (mantém 70% de cima, centralizado, e tira a faixa de baixo). Conferir antes de usar: o rosto tem que caber no recorte
21. **Fonte com cartela de texto própria** (Calabrez/NeuroVox: tela preta com a frase escrita): a nossa legenda ficava por cima da dele. Achar com uma folha de quadros (1 por segundo) dos trechos. Solução: `"sem_legenda": [[ini, fim]]` (tempo na fonte) no `trechos.json`, que esconde a nossa legenda só ali. Também: com folga curta, a última legenda de um trecho sobrepunha a primeira do seguinte, e agora o `montar.py` corta a anterior

## Shorts (cortes verticais 9:16)

**Crédito do streamer em cortes da Kick.** Antes de postar no YouTube, YouTube Shorts ou TikTok, borrar o nome e o logo da Kick sempre que aparecerem no vídeo. Deixar apenas o `@` do streamer como crédito visível na tela.

22. **Script:** `corte_vertical.py <pasta> <n> "<TÍTULO DO TOPO>" [zoom] [desloc_x] [desloc_y] [gamma]` usa o `build/segNN.mp4` (já em P&B e com o áudio nivelado), transcreve, legenda em pé, título fixo no topo e música com ducking. Upload com `node scripts/publicar_youtube.js <pasta> cortes/publicar-NN.json`
23. **Palestrante que anda no palco ou aparece pequeno não serve pra Short** (Cortella no vídeo do medo: aparecia na esquerda, no meio e na direita, e o zoom cortou a cabeça). Antes de escolher, olhar 3 quadros do trecho com a caixa 9:16 no centro. Preferir quem fala de frente pra câmera (Karnal, Calabrez, Clóvis no estúdio)
24. **Marca d'água do canal de origem** ("@MENTALISTASERIE" no canto da cena): achar recortando o canto de um quadro de cada fonte. Solução: `"delogo": "x:y:w:h"` no trecho (coordenadas na fonte 1080p)
25. **Cena de série é escura** e o P&B padrão do canal (contraste 1.32, brilho -0.07) apagava os rostos. Solução: `config.json` na pasta do vídeo com `{"cor": "..."}`. Pra série: `hue=s=0,eq=contrast=1.12:brightness=0.03:gamma=1.18,vignette=angle=PI/5` (aprovado pelo dono no vídeo do Patrick Jane)
26. **Short de cena de série** (duas pessoas, uma em cada lado da tela): o recorte 9:16 do centro pegava metade de cada uma. Solução: opção `faixa` no `corte_vertical.py` (cena inteira no meio, fundo preto, título em cima, legenda embaixo). E `de=`/`ate=` pra ficar **abaixo de 60s**: Short com reivindicação de direitos autorais e mais de 1 minuto é bloqueado

## Lições do vídeo "Ganância" (2026-10-17)

27. **YouTube bloqueou o yt-dlp** ("Sign in to confirm you're not a bot") depois de poucas requisições seguidas. `--cookies-from-browser chrome` não funciona com o Chrome aberto (banco travado) e o Edge dá erro de DPAPI. O bloqueio é por rajada e passa sozinho: esperar 20s entre vídeos (não 4s) e tentar de novo com espera crescente (40s, 80s...). O cliente `web_safari` passa do bloqueio mas não entrega vídeo nem legenda (só serve pra título/canal)
28. **Cenas de filme dublado em canal de fã costumam ser 360p** (Felipe Stud10s: Scarface inteiro em cenas, 364p). Pra cena de filme, procurar primeiro o canal oficial de clipes em português (Boxoffice BR, `UCLzcJYbuvM8b8kW_7BvNjMA`, 4K)

## Lições do vídeo "Ganância" (2026-10-20)

29. **`montar.py` com caminho relativo** (`marketing/youtube/...`) gera o `seg00.mp4` mas o render final diz "No such file" (mistura `/` com `\`). Solução: passar o caminho completo, `marketing/youtube/<pasta>`
30. **Cortella tinha duas cópias do mesmo vídeo** (Radar de Negócios 720p e motivaremos 1080p, mesmos tempos). Quando a fonte vier abaixo de 1080p, procurar outra cópia antes de aceitar
31. **Repost de canal de motivação não mostra o palestrante** (motivaremos/Radar de Negócios, Cortella "Ambição x Ganância"): só imagens de banco, tela preta, cartelas próprias e marca d'água fixa ("MOTIVAREMOS", "SE INSCREVA E INSPIRE-SE"). Achar olhando uma folha de quadros da fonte **antes de propor os trechos**. Preferir o canal oficial do palestrante. Se só existir o repost, tampar as marcas com `"delogo": ["x:y:w:h", ...]` (agora aceita lista)
32. **Canal oficial também tem cartela preta com a frase** (Canal do Cortella/Sophya, Kant em 36–42 s): `"cobrir"` com outro momento da fonte. Cartelas verdes por cima do palestrante (Hillel): `"sem_legenda"`
33. **Fonte vertical (608x1080)** no meio de vídeo horizontal não serve (corta quase tudo). Conferir largura x altura com ffprobe antes de usar

## Lições do vídeo "Thomas Shelby" (2026-10-26)

34. **Cena de fã com faixa branca no topo** (Fídel Timana, ~21 px) + logos BBC/canal nos cantos + legenda embutida embaixo: `"recorte": 0.7` tira logos e legenda, e `"topo": 24` pula a faixa. A cena escura de série ganha `"cor"` só nela (P&B claro da lição 25), sem clarear os palestrantes
35. **Netflix Brasil não tem legenda automática em pt** nos clipes: o yt-dlp "dá certo" mas não grava nada. Conferir se o `.vtt` apareceu na pasta
36. **Versão vertical da mesma cena** (Kaique Sampaio, 576x1024) aparece primeiro na busca. Sempre conferir largura x altura
37. **Borda comeu palavra mesmo com `bordas.py` ok** ("fazer" no fim, "Não" no começo): o Whisper atrasa e a pausa mais perto cai do lado errado. Achar no vídeo final transcrevendo de novo. Solução: `"fala_ini"`/`"fala_fim"` no trecho (tempo exato na fonte, tirado do silencedetect com `-35dB:d=0.08`), refazer o seg e transcrever só ele pra confirmar. Se um Short usa esse seg, refazer o Short também


## Lições do corte da live do Gaules (2026-11-15)

38. **PC travou e desligou montando o vídeo de 10 min** com um filtro só no ffmpeg (`trim` de 10 trechos da mesma live de 20 min + `concat`). O ffmpeg decodifica a live inteira e guarda na RAM os quadros 1080p60 de todos os trechos esperando a vez deles: a memória acaba. O teste com 2 trechos passou, por isso não deu pra ver antes. Solução: **um trecho por vez**, com `-ss <ini> -t <dur>` ANTES do `-i` (só lê o pedaço), salvo em `build/segNN.mp4`; depois juntar com o concat demuxer (`-f concat -i lista.txt`) e queimar legenda + loudnorm numa passada final. Nunca juntar muitos `trim` da mesma fonte longa num filtro só
39. **`drawtext` sem `fontfile` dá "Fontconfig error"** no ffmpeg do Windows. Usar legenda ASS (`subtitles=...:fontsdir='C\:/Windows/Fonts'`) ou passar `fontfile=C\:/Windows/Fonts/arialbd.ttf`
40. **A câmera do Gaules muda de lugar:** no jogo/menu do CS fica à esquerda (380x215 em x=0, y=474); no site da Gamers Club fica embaixo à direita (410x232 em x=1510, y=848). Conferir quadros do trecho antes de recortar a câmera

## HyperFrames — fonte em subcomposição (2026-11-15)

41. **A validação `font_family_without_font_face` pode falhar em uma subcomposição mesmo que a fonte exista na composição principal.** Declarar `@font-face` também no estilo dentro do `<template>` que usa a família. Apontar para a fonte local com caminho a partir da raiz do projeto, por exemplo `assets/titulo.ttf`, e rodar `hyperframes check` de novo.

## Gravação de lives (2026-11-16)

42. **O Streamlink rejeita `00:120:00` como duração.** O `gravar_lives.py` converte `--teste 120` para `02:00:00` separando horas e minutos com `divmod`.

## Cortes de GTA 6 (2026-11-18)

43. **A trilha do próprio GTA 6 dá Content ID, não só a rádio.** No 1º episódio do Paulinho (G8JcRu6trTs) vieram 3 reivindicações de áudio: "Searching" (Change), uma música sem nome (Because Music) e "Jump Into the Fire" (Harry Nilsson). Elas tocaram na abertura/créditos do jogo e numa cena de missão. Não é strike nem bloqueio, só tira a receita. Solução: no Studio, em cada reivindicação, "Tomar providências" → "Silenciar música" → "Silenciar só a música" (mantém a voz). Nos próximos: ao montar, conferir a abertura e as cenas com música e abaixar ou cortar esses trechos antes de subir.

## Padrão de episódio de GTA aprovado pelo dono (vídeo do pé grande do Gabepeixe, 2026-11-18)

44. **Abertura que segura sem entregar o momento (SÓ NO SEGUNDO CANAL; no canal principal o vídeo começa direto, sem abertura nem tela).** O dono não gostou de mostrar o momento do título logo no começo, porque a pessoa vê e sai. Padrão dos episódios do segundo canal:
    1. **0:00 a ~0:06:** só a REAÇÃO do streamer (zoom na webcam), 1 ou 2 falas fortes do momento do título. Nunca mostrar o jogo nesse momento (o bicho, a cena, o acontecimento)
    2. **~3 s de tela "NAS PRÓXIMAS CENAS..."** (jogo borrado e escuro, texto branco no meio). No `montar_gta.py`: trecho `{"ini": X, "fim": X+3.2, "card": ["NAS PRÓXIMAS CENAS..."]}`
    3. Depois, a história em ordem desde o começo (missão, contexto), até o momento e a conclusão
45. **Baixar trecho de live da Kick:** o Streamlink ignora `--hls-start-offset` na Kick e grava o ao vivo de agora. Solução: pegar o link da gravação em `https://kick.com/api/v2/channels/<canal>/videos` (campo `source`, existe mesmo com a live rolando), trocar `master.m3u8` por `1080p60/playlist.m3u8` e baixar com `ffmpeg -ss H:MM:SS -i <link> -t MM:SS -c copy`. A legenda pt da Kick (`subtitles/pt/playlist.m3u8`) vem com cada frase repetida várias vezes, serve só pra achar os momentos; pra cortar, usar o Whisper
46. **O tempo do player da Kick ao vivo fica uns 2,5 min atrás do tempo da gravação.** Quando o dono mandar um print com o tempo, conferir com quadros da gravação antes de cortar
47. **Logo da Kick na faixa da webcam do Gabepeixe:** `"borrar": [[1786, 294, 24, 24]]` no `episodio.json` (aplicado antes do zoom)

48. **Gravação da live no YouTube sai fraca (3,6 Mbps, rosto da webcam borrado no Short).** Usar o VOD do canal do streamer: `yt-dlp -f "623+140/308+140" --download-sections "*INI-FIM"` (1440p VP9, ~10 Mbps). Achar o tempo certo no VOD cruzando o áudio (FFT) de um trecho da gravação com 40 min de áudio do VOD (`-f 140`). Na fonte 1440p, multiplicar os crops por 1,333 e tirar o `hqdn3d`. Faixa azul do canal principal: `identidade/shorts/faixa-azul.png`

49. **O TS pode desaparecer durante a análise quando a conversão do gravador termina.** Na live 2 do Paulinho (2026-11-19), o TS de 7,4 GB foi substituído pelo MP4 enquanto a transcrição rodava. Se surgir 'No such file', listar a pasta antes de tratar como perda: conferir duração e streams do MP4, trocar a fonte e retomar dos blocos salvos. Não refazer nem apagar os blocos válidos.

50. **SetPriorityClass via ctypes em Python 64 bits pode retornar WinError 0xc0000008 se o HANDLE for tratado como inteiro de 32 bits.** Declarar GetCurrentProcess.restype = ctypes.c_void_p e SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong] antes da chamada. Usado na análise e montagem do episódio da emboscada do Paulinho (2026-11-19).

51. **Retomar um checkpoint pode deixar 1 s de tela preta do jogo com a webcam ainda visível.** O blackdetect na tela inteira pode ignorar o defeito por causa da webcam. Conferir também a área principal do jogo (neste episódio: crop=1400:800:510:100). No Paulinho emboscada, 06:56.10–06:57.20 foi coberto pela reação real ampliada, preservando todo o áudio; nova checagem passou sem preto ou silêncio prolongado.
`n52. **Legendas ASS podem se sobrepor na passagem entre grupos de palavras.** O acréscimo de 0,15 s ao último destaque invadia o grupo seguinte nos Shorts do Paulinho (19/11/2026). Limitar o fim de cada evento Caption ao início do próximo, inclusive entre grupos; regenerar os trechos e conferir os quadros finais.

## Compilação de vários streamers (easter eggs, 2026-11-20)

53. **`delogo` falha se a caixa encostar na borda da tela** (x=0, y=0 ou x+w=1920, y+h=1080): o ffmpeg dá "Invalid argument" e o `montar_gta.py` para no trecho. Manter cada caixa de `borrar` entre 1 e 1918 (largura) e entre 1 e 1078 (altura). Contador da Kick: Bistecone `[1690,1,228,40]`, Gabe `[1770,1005,146,70]`
54. **Compilação com várias lives:** o `montar_gta.py` aceita `fonte`, `cam`, `zoom_caixa`, `borrar`, `streamer` e `censura` em cada trecho. A transcrição de cada fonte fica em `transcricoes/<nome-da-fonte>.json`. Tempo de um clipe da Kick dentro da VOD: `started_at` do clipe (`/api/v2/clips/<id>`) menos `start_time` da VOD (`/api/v2/channels/<canal>/videos`)
55. **Tela preta do jogo (desmaio) e menu de pausa no meio do momento** (Davy no Pé Grande, Gabe no jacaré): cobrir com `zoom` na reação nesses segundos, sem cortar o áudio. Achar com blackdetect na área do jogo e com folha de quadros a cada 2 s
56. **Mesma missão em dois streamers** (tubarão do Bistecone e do Coringa = missão do Dobbs): numa compilação, usar só um
57. **NPC pelado (abdução do Davy):** `"censura": [[x, y, w, h, ini, fim]]` (borrão forte, tempos na fonte), deixando a webcam livre
