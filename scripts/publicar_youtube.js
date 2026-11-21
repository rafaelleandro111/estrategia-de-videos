// Sobe um vídeo pro canal logado no AgentTube e deixa privado, agendado ou público.
// Uso: node scripts/publicar_youtube.js <pasta-do-video> [arquivo.json]
// A pasta precisa ter publicar.json (ou o arquivo indicado, ex.: cortes/publicar-01.json pra Short):
//   { video, thumb?, titulo, descricao, tags[], categoria?, agendar? ("2026-10-15T18:00:00-03:00") }
// Com "agendar", o vídeo fica privado até a hora e o YouTube publica sozinho.
// Para publicar na hora, use publicarAgora: true e informe canalId.
// Outro canal: acrescente --canal segundo (usa config/tokens-segundo.json). Padrão: canal principal (tokens.json).
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
  // 2º argumento opcional: outro arquivo de dados (ex.: cortes/publicar-01.json pra Shorts)
  const metaPath = path.join(pasta, ARGS[1] || 'publicar.json');
  const meta = JSON.parse(fs.readFileSync(metaPath, 'utf8'));
  if (meta.youtubeId) throw new Error(`Já enviado: https://youtu.be/${meta.youtubeId}`);

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

  const agora = meta.publicarAgora === true;
  if (agora) {
    if (!meta.canalId || meta.agendar) {
      throw new Error('Para publicar agora, informe canalId e deixe agendar vazio.');
    }
    const canais = await yt.channels.list({ part: 'id', mine: true });
    if (canais.data.items?.length !== 1 || canais.data.items[0].id !== meta.canalId) {
      throw new Error('O canal autenticado não corresponde ao canal informado.');
    }
  }
  const status = { privacyStatus: agora ? 'public' : 'private', selfDeclaredMadeForKids: false, containsSyntheticMedia: false };
  if (meta.agendar) {
    const quando = new Date(meta.agendar);
    if (!(quando.getTime() > Date.now() + 15 * 60000)) throw new Error(`Horário de agendamento no passado: ${meta.agendar}`);
    status.publishAt = quando.toISOString();
  }

  const videoPath = path.join(pasta, meta.video);
  const total = fs.statSync(videoPath).size;
  let ultimo = -1;
  const res = await yt.videos.insert(
    {
      part: 'snippet,status',
      requestBody: {
        snippet: {
          title: meta.titulo,
          description: meta.descricao,
          tags: meta.tags,
          categoryId: meta.categoria || '22',
          defaultLanguage: 'pt-BR',
          defaultAudioLanguage: 'pt-BR',
        },
        status,
      },
      media: { body: fs.createReadStream(videoPath) },
    },
    {
      onUploadProgress: (e) => {
        const p = Math.floor((e.bytesRead / total) * 100);
        if (p !== ultimo && p % 10 === 0) { ultimo = p; console.log(`upload ${p}%`); }
      },
    }
  );
  const id = res.data.id;
  meta.youtubeId = id;
  fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2));
  console.log(`Enviado: https://youtu.be/${id} | ${res.data.status.privacyStatus}` +
    (res.data.status.publishAt ? ` | publica em ${res.data.status.publishAt}` : ''));

  const thumb = meta.thumb && path.join(pasta, meta.thumb);
  if (thumb && fs.existsSync(thumb)) {
    try {
      await yt.thumbnails.set({ videoId: id, media: { body: fs.createReadStream(thumb) } });
      console.log('Thumb definida.');
    } catch (e) {
      console.log(`Thumb NÃO definida: ${e.message} (canal precisa estar verificado: youtube.com/verify)`);
    }
  } else if (meta.thumb) {
    console.log(`Thumb ainda não existe (${meta.thumb}). Subir depois pelo Studio.`);
  }
}

main().catch((e) => { console.error('ERRO:', e.message); process.exit(1); });
