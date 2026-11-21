// Atualiza título, descrição, tags e categoria de um vídeo JÁ enviado, a partir do publicar.json.
// Uso: node scripts/atualizar_video.js <pasta-do-video> [arquivo.json] [--canal segundo]
// O json precisa ter "youtubeId" (gravado pelo publicar_youtube.js). Não mexe em agendamento nem privacidade.
const path = require('path');
const fs = require('fs');

const AGENT = path.join(__dirname, '..', 'ferramentas', 'youtube-automation-agent');
const { google } = require(path.join(AGENT, 'node_modules', 'googleapis'));

const ARGS = process.argv.slice(2);
const iCanal = ARGS.indexOf('--canal');
const CANAL = iCanal >= 0 ? ARGS.splice(iCanal, 2)[1] : 'principal';
const TOKFILE = CANAL === 'principal' ? 'tokens.json' : `tokens-${CANAL}.json`;

async function main() {
  const pasta = path.resolve(ARGS[0] || '.');
  const meta = JSON.parse(fs.readFileSync(path.join(pasta, ARGS[1] || 'publicar.json'), 'utf8'));
  if (!meta.youtubeId) throw new Error('Esse json não tem youtubeId (vídeo ainda não foi enviado).');

  const cred = JSON.parse(fs.readFileSync(path.join(AGENT, 'config', 'credentials.json'), 'utf8')).youtube;
  const tokensPath = path.join(AGENT, 'config', TOKFILE);
  const tokens = JSON.parse(fs.readFileSync(tokensPath, 'utf8'));
  const auth = new google.auth.OAuth2(cred.client_id, cred.client_secret, cred.redirect_uris[0]);
  auth.setCredentials(tokens.youtube);
  auth.on('tokens', (t) => {
    tokens.youtube = { ...tokens.youtube, ...t };
    fs.writeFileSync(tokensPath, JSON.stringify(tokens, null, 2));
  });
  const yt = google.youtube({ version: 'v3', auth });

  const res = await yt.videos.update({
    part: ['snippet'],
    requestBody: {
      id: meta.youtubeId,
      snippet: {
        title: meta.titulo,
        description: meta.descricao,
        tags: meta.tags,
        categoryId: meta.categoria || '22',
        defaultLanguage: 'pt-BR',
        defaultAudioLanguage: 'pt-BR',
      },
    },
  });
  console.log(`Atualizado: https://youtu.be/${res.data.id} | "${res.data.snippet.title}"`);
}

main().catch((e) => { console.error('ERRO:', e.message); process.exit(1); });
