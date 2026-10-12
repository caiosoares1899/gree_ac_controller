'use strict';
// Descobre os Gree da rede: manda um broadcast {"t":"scan"} na UDP 7000 e lista quem responde (IP + id do aparelho).
const dgram = require('dgram');
const s = dgram.createSocket('udp4');
const achados = new Map();
s.on('message', (msg, rinfo) => {
  try { const j = JSON.parse(msg.toString()); if (j.t === 'dev' || j.cid) achados.set(rinfo.address, j.cid || j.mac || '?'); } catch (e) {}
});
s.bind(() => {
  s.setBroadcast(true);
  s.send('{"t":"scan"}', 7000, '255.255.255.255');
  setTimeout(() => {
    if (!achados.size) console.log('Nenhum Gree respondeu. PC e aparelhos estão na mesma rede/Wi-Fi? (o firewall do Windows pode bloquear UDP — libere o Node).');
    for (const [ip, id] of achados) console.log(ip, ' ', id);
    s.close();
  }, 3000);
});
