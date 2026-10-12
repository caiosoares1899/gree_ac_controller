'use strict';
// Descobre os Gree da rede. Por cada placa de rede IPv4 do PC:
//   1) manda broadcast {"t":"scan"} na UDP 7000 (broadcast da sub-rede dela);
//   2) varre a sub-rede inteira (/24) em unicast — pega aparelhos que ignoram broadcast.
// Uso:  node descobrir.js                (todas as placas)
//       node descobrir.js 192.168.0.50   (testa só esse IP — o do aparelho, que dá pra ver no roteador)
const dgram = require('dgram');
const os = require('os');

const alvoUnico = process.argv[2];
const achados = new Map();
const MSG = Buffer.from('{"t":"scan"}');

const placas = [];
for (const [nome, lista] of Object.entries(os.networkInterfaces()))
  for (const i of lista || []) if (i.family === 'IPv4' && !i.internal) placas.push({ nome, ip: i.address, mask: i.netmask });

console.log('Placas de rede do PC:');
placas.forEach(p => console.log('  ', p.ip.padEnd(16), p.mask.padEnd(16), p.nome));
if (!placas.length) { console.log('Nenhuma placa de rede ativa.'); process.exit(1); }

const aInt = ip => ip.split('.').reduce((a, b) => (a << 8) + (+b), 0) >>> 0;
const aIp = n => [n >>> 24, (n >>> 16) & 255, (n >>> 8) & 255, n & 255].join('.');

function varre(p) {
  return new Promise(resolve => {
    const s = dgram.createSocket('udp4');
    s.on('error', () => { try { s.close(); } catch (e) {} resolve(); });
    s.on('message', (msg, r) => {
      try { const j = JSON.parse(msg.toString()); if (j.t === 'dev' || j.cid || j.t === 'pack') achados.set(r.address, j.cid || j.mac || '(respondeu)'); } catch (e) {}
    });
    s.bind(0, p.ip, () => {
      if (alvoUnico) s.send(MSG, 7000, alvoUnico);
      else {
        s.setBroadcast(true);
        const rede = (aInt(p.ip) & aInt(p.mask)) >>> 0, bcast = (rede | (~aInt(p.mask) >>> 0)) >>> 0;
        s.send(MSG, 7000, aIp(bcast));
        s.send(MSG, 7000, '255.255.255.255');
        // unicast pra cada IP do /24 em que o PC está
        const base = (aInt(p.ip) & 0xFFFFFF00) >>> 0;
        for (let n = 1; n < 255; n++) { const ip = aIp((base | n) >>> 0); if (ip !== p.ip) s.send(MSG, 7000, ip); }
      }
      setTimeout(() => { try { s.close(); } catch (e) {} resolve(); }, 4000);
    });
  });
}

(async () => {
  await Promise.all(placas.map(varre));
  console.log('\nResultado:');
  if (!achados.size) {
    console.log('  Nenhum Gree respondeu.');
    console.log('  • Aparelho e PC precisam estar na MESMA rede (mesmo roteador/Wi-Fi, mesma faixa de IP, sem "isolamento de clientes"/rede de convidados).');
    console.log('  • Libere o Node no Firewall do Windows (UDP) e desligue VPN.');
    console.log('  • Se souber o IP do aparelho (veja no roteador), teste direto:  node descobrir.js 192.168.0.50');
  }
  for (const [ip, id] of achados) console.log('  ', ip.padEnd(16), id);
})();
