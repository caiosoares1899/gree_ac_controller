'use strict';
// Ponte Gree ⇄ Firebase. Roda no PC de casa (sempre ligado):
//   • lê os comandos que o app grava em gree/comandos/{id} e manda pro aparelho por UDP (rede local, sem nuvem da Gree);
//   • publica o estado do aparelho em gree/aparelhos/{id} e o histórico ("quem mexeu") em gree/historico/{id}.
const fs = require('fs');
const path = require('path');
const admin = require('firebase-admin');
const Gree = require('gree-hvac-client');

const cfgPath = path.join(__dirname, 'config.json');
if (!fs.existsSync(cfgPath)) { console.error('Falta o config.json — copie o config.example.json e preencha (veja o README).'); process.exit(1); }
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
admin.initializeApp({
  credential: admin.credential.cert(require(path.resolve(__dirname, cfg.serviceAccount))),
  databaseURL: cfg.databaseURL,
});
const db = admin.database();

// O que o app pode pedir — qualquer outra coisa é descartada (o comando vem de um navegador).
const PERMITIDO = {
  power: ['on', 'off'],
  mode: ['auto', 'cool', 'heat', 'dry', 'fan_only'],
  fanSpeed: ['auto', 'low', 'mediumLow', 'medium', 'mediumHigh', 'high'],
  turbo: ['on', 'off'],
  quiet: ['off', 'mode1', 'mode2', 'mode3'],
  lights: ['on', 'off'],
  swingVert: ['default', 'full', 'fixedTop', 'fixedMidTop', 'fixedMid', 'fixedMidBottom', 'fixedBottom'],
};
function limpa(cmd) {
  const out = {};
  if (Number.isInteger(cmd.temperature) && cmd.temperature >= 16 && cmd.temperature <= 30) out.temperature = cmd.temperature;
  for (const k of Object.keys(PERMITIDO)) if (PERMITIDO[k].includes(cmd[k])) out[k] = cmd[k];
  return out;
}

const CAMPOS = ['power', 'mode', 'temperature', 'fanSpeed', 'turbo', 'quiet', 'lights', 'swingVert'];
const AGORA = () => admin.database.ServerValue.TIMESTAMP;

function sobe(ap) {
  const id = ap.id;
  const client = new Gree.Client({ host: ap.host, pollingInterval: 2000, pollingTimeout: 2500 });
  let ultimo = {};                 // último estado visto (pra só registrar o que mudou)
  const pendentes = {};            // campo → { valor, quem, uid, ate } — comandos que enviamos e ainda não vimos refletidos
  const refAp = db.ref('gree/aparelhos/' + id);
  const marcaOnline = on => refAp.update({ online: on, atualizado: AGORA() }).catch(() => {});

  refAp.update({ nome: ap.nome });

  client.on('connect', () => { console.log(`[${id}] conectado (${client.getDeviceId()})`); marcaOnline(true); });
  client.on('no_response', () => marcaOnline(false));
  client.on('disconnect', () => marcaOnline(false));
  client.on('error', e => console.warn(`[${id}] erro:`, e && e.message));

  client.on('update', (mudou, props) => {
    const estado = { currentTemperature: props.currentTemperature };
    for (const k of CAMPOS) estado[k] = props[k];
    refAp.update({ estado, online: true, atualizado: AGORA() }).catch(() => {});

    // Histórico: cada campo que mudou. Se foi a gente que mandou (pendente), atribui a quem; senão foi o controle remoto/botão/app da Gree.
    const t = Date.now();
    for (const k of Object.keys(mudou)) {
      if (!CAMPOS.includes(k) || ultimo[k] === undefined) continue;     // 1ª leitura não é mudança
      const p = pendentes[k];
      const meu = p && p.ate > t && p.valor === mudou[k];
      if (meu) delete pendentes[k];
      db.ref('gree/historico/' + id).push({
        campo: k, de: ultimo[k], para: mudou[k], ts: AGORA(),
        quem: meu ? p.quem : 'Controle remoto', uid: meu ? p.uid : null, origem: meu ? 'app' : 'aparelho',
      }).catch(() => {});
    }
    ultimo = { ...ultimo, ...Object.fromEntries(CAMPOS.map(k => [k, props[k]])) };
  });

  // Comandos do app (fila): aplica e apaga.
  db.ref('gree/comandos/' + id).on('child_added', async snap => {
    const cmd = snap.val() || {};
    snap.ref.remove().catch(() => {});
    if (cmd.ts && Date.now() - cmd.ts > 60000) return;          // comando velho (PC ficou fora do ar): não executa de surpresa
    const patch = limpa(cmd);
    if (!Object.keys(patch).length) return;
    const quem = String(cmd.quem || 'Alguém').slice(0, 40);
    for (const [k, v] of Object.entries(patch)) pendentes[k] = { valor: v, quem, uid: cmd.uid || null, ate: Date.now() + 15000 };
    try { await client.setProperties(patch); console.log(`[${id}]`, quem, patch); }
    catch (e) { console.warn(`[${id}] não enviou:`, e && e.message); marcaOnline(false); }
  });
}

cfg.aparelhos.forEach(sobe);
process.on('unhandledRejection', e => console.warn('unhandledRejection', e && e.message));
console.log('Ponte Gree no ar — aparelhos:', cfg.aparelhos.map(a => a.id).join(', '));
