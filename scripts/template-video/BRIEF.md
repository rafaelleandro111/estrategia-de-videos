---
workflow: general-video
flow: companion
storyboard: yes
message: "Uma IA tentando criar algo de verdade, nível por nível, e você descobre se ela consegue"
destination: youtube
aspect: 1920x1080
language: pt-BR
voice: kokoro/pm_santa
length: variável (vídeo longo 10-20 min; template)
angle: template reutilizável
---

## Intent

Template fixo do canal. Cada vídeo segue a escada de níveis
(fácil → médio → impossível) com gravação de tela real do agente de IA trabalhando,
narração Kokoro (pm_santa), legendas e zooms. Objetivo principal: renderizar cada
vídeo novo com um script local (`montar.py` + `video.json`), sem gastar tokens do
Claude na edição.

## Assets

- (pendente) gravação de tela de teste, 1 a 2 min, de uma IA criando algo. Até chegar, usar placeholder gerado por FFmpeg.

## Customizations

- Visual "terminal hacker": fundo preto esverdeado, verde neon, fonte monoespaçada.
- Variante 9:16 para cortes (TikTok, Reels, Shorts), renderizada na vertical.
- Toda cartela/abertura/veredito/encerramento é parametrizada por variáveis.

## Notes

- Mostrar o erro: o veredito "DEU ERRADO" é parte do formato, não exceção.
- Thumb fica fora deste template.
- Referência de formato: Caverna da IA (escada de níveis, plot twist final).
