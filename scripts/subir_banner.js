// Sobe o banner (imagem do canal) pro canal logado no AgentTube.
// Uso: node scripts/subir_banner.js [caminho-do-png] [--canal segundo]
// Padrão: identidade/banner/banner.png no canal principal (@seucanal). segundo canal = @segundocanal.
// Só troca o banner; mantém nome, descrição e o resto da personalização do canal.
const path = require('path');
const fs = require('fs');

const AGENT = path.join(__dirname, '..', 'ferramentas', 'youtube-automation-agent');
const { google } = require(path.join(AGENT, 'node_modules', 'googleapis'));

const CANAIS = { principal: ['tokens.json', '@seucanal'], segundo: ['tokens-segundo.json', '@segundocanal'] };
const ARGS = process.argv.slice(2);
const iCanal = ARGS.indexOf('--canal');
const CANAL = iCanal >= 0 ? ARGS.splice(iCanal, 2)[1] : 'principal';
if (!CANAIS[CANAL]) { console.error(`Canal desconhecido: ${CANAL}. Use: ${Object.keys(CANAIS).join(', ')}`); process.exit(1); }
const [TOKFILE, HANDLE] = CANAIS[CANAL];

async function main() {
  const img = path.resolve(ARGS[0] || path.join(__dirname, '..', 'identidade', 'banner', 'banner.png'));
  const handle = HANDLE;

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

  // 1. Confere o canal logado
  const canais = await yt.channels.list({ part: 'id,snippet,brandingSettings', mine: true });
  const canal = canais.data.items?.[0];
  if (!canal) throw new Error('Nenhum canal no login atual.');
  const atual = (canal.snippet.customUrl || '').toLowerCase();
  if (atual !== handle) throw new Error(`Canal logado é ${atual || canal.snippet.title}, não ${handle}. Nada foi alterado.`);
  console.log(`Canal: ${canal.snippet.title} (${atual})`);

  // 2. Envia a imagem
  const up = await yt.channelBanners.insert({
    media: { mimeType: 'image/png', body: fs.createReadStream(img) },
  });
  const url = up.data.url;
  console.log('Imagem enviada.');

  // 3. Aplica no canal, mantendo o resto da personalização
  const branding = canal.brandingSettings || {};
  branding.image = { ...(branding.image || {}), bannerExternalUrl: url };
  await yt.channels.update({
    part: 'brandingSettings',
    requestBody: { id: canal.id, brandingSettings: { channel: branding.channel, image: branding.image } },
  });
  console.log(`Banner trocado: https://www.youtube.com/${atual}`);
}

main().catch((e) => {
  console.error('ERRO:', e.response?.data?.error?.message || e.message);
  process.exit(1);
});
