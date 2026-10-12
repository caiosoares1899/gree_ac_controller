"""Serviço 100% online: Firebase ⇄ nuvem da Gree (login Gree+ + MQTT), sem nada ligado em casa.

  • lê os comandos que a página grava em gree/comandos/{id} e manda pra nuvem da Gree;
  • publica o estado real em gree/aparelhos/{id} e o histórico ("quem mexeu") em gree/historico/{id}.
Mesmo formato de dados da bridge/ local — o index.html não muda.
"""
import asyncio
import json
import logging
import os
import re
import time

import firebase_admin
from firebase_admin import credentials, db
from greeclimate_davo22.cloud_discovery import CloudDiscovery
from greeclimate_davo22.device import FanSpeed, Mode, VerticalSwing

from mapeamento import CAMPOS, aplica_patch, comandos_do_evento, estado_de, limpa_patch

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gree")

GREE_USER = os.environ["GREE_USER"]
GREE_PASS = os.environ["GREE_PASS"]
GREE_SERVER = os.environ.get("GREE_SERVER", "South American")
DB_URL = os.environ["FIREBASE_DB_URL"]
POLL = int(os.environ.get("POLL_SECONDS", "10"))
# SOMENTE_LEITURA=1: lê e publica o estado, mas IGNORA todos os comandos da página (bom pra 1º teste / de madrugada)
SOMENTE_LEITURA = os.environ.get("SOMENTE_LEITURA", "0") == "1"
# "9424b8ab167f=Quarto,aabbccddeeff=Sala" — nomes bonitos (senão usa o nome que a Gree dá, ex. AC167f)
NOMES = dict(p.split("=", 1) for p in os.environ.get("GREE_NOMES", "").split(",") if "=" in p)


def iniciar_firebase():
    bruto = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    cred = credentials.Certificate(json.loads(bruto) if bruto else os.environ.get("FIREBASE_CREDENTIALS_PATH", "service-account.json"))
    firebase_admin.initialize_app(cred, {"databaseURL": DB_URL})


async def fb(fn, *a, **kw):
    return await asyncio.to_thread(fn, *a, **kw)      # firebase_admin é bloqueante


def agora():
    return int(time.time() * 1000)


class Aparelho:
    def __init__(self, id_, nome, dev):
        self.id, self.nome, self.dev = id_, nome, dev
        self.lock = asyncio.Lock()          # a lib não enfileira comandos sozinha
        self.ultimo = {}
        self.pendentes = {}                 # campo → (valor, quem, uid, até) dos comandos que nós enviamos
        self.falhas = 0

    async def publicar(self, online=True):
        estado = estado_de(self.dev)
        t = agora()
        for k in CAMPOS:
            if k in self.ultimo and self.ultimo[k] != estado[k]:
                p = self.pendentes.get(k)
                meu = bool(p and p[3] > t and p[0] == estado[k])
                if meu:
                    del self.pendentes[k]
                await fb(db.reference("gree/historico/" + self.id).push, {
                    "campo": k, "de": self.ultimo[k], "para": estado[k], "ts": t,
                    "quem": p[1] if meu else "Controle remoto", "uid": p[2] if meu else None,
                    "origem": "app" if meu else "aparelho"})
        self.ultimo = {k: estado[k] for k in CAMPOS}
        await fb(db.reference("gree/aparelhos/" + self.id).update,
                 {"nome": self.nome, "estado": estado, "online": online, "atualizado": t})

    async def atualizar(self):
        async with self.lock:
            await self.dev.update_state()
        await self.publicar()

    async def comando(self, cmd):
        patch = limpa_patch(cmd)
        if not patch:
            return
        quem = str(cmd.get("quem") or "Alguém")[:40]
        for k, v in patch.items():
            self.pendentes[k] = (v, quem, cmd.get("uid"), agora() + 20000)
        async with self.lock:
            aplica_patch(self.dev, patch, Mode, FanSpeed, VerticalSwing)
            await self.dev.push_state_update()
            await self.dev.update_state()
        log.info("[%s] %s → %s", self.id, quem, patch)
        await self.publicar()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower()) or "ar"


async def sessao(fila):
    """Uma sessão = um login na nuvem. Se cair, o supervisor abre outra."""
    disc = CloudDiscovery(username=GREE_USER, password=GREE_PASS, server=GREE_SERVER)
    aparelhos = {}
    try:
        log.info("Entrando na nuvem da Gree (%s)…", GREE_SERVER)
        infos = await disc.scan()
        loop = asyncio.get_running_loop()
        for info in infos:
            dev = None
            for cifra in (1, 2):                                   # 1 = AES-ECB (comum), 2 = AES-GCM (módulos novos)
                try:
                    dev = await disc.create_device(info, cipher_version=cifra)
                    await dev.bind()
                    break
                except Exception as e:
                    log.warning("[%s] cifra v%s falhou: %s", info.name, cifra, e)
                    dev = None
            if dev is None:
                continue
            nome = NOMES.get(info.mac, info.name)
            ap = Aparelho(slug(nome), nome, dev)
            orig = dev.handle_state_update

            def novo(*a, _orig=orig, _ap=ap, **kw):                # estado empurrado pela nuvem (ex.: alguém usou o controle)
                r = _orig(*a, **kw)
                loop.call_soon(lambda: loop.create_task(_ap.publicar()))
                return r
            dev.handle_state_update = novo
            aparelhos[ap.id] = ap
            await ap.publicar(online=bool(info.online))
            log.info("Aparelho pronto: %s (%s)", nome, info.mac)
        if not aparelhos:
            raise RuntimeError("nenhum aparelho utilizável na conta")

        async def consumir():
            while True:
                apid, pid, cmd = await fila.get()
                await fb(db.reference("gree/comandos/%s/%s" % (apid, pid)).delete)
                if agora() - int(cmd.get("ts") or 0) > 60000:      # comando velho (serviço ficou fora): não executa de surpresa
                    continue
                if SOMENTE_LEITURA:
                    log.info("[%s] modo só leitura: comando ignorado (%s)", apid, limpa_patch(cmd))
                    continue
                ap = aparelhos.get(apid)
                if ap:
                    try:
                        await ap.comando(cmd)
                    except Exception as e:
                        log.warning("[%s] comando falhou: %s", apid, e)

        async def vigiar():
            while True:
                await asyncio.sleep(POLL)
                for ap in aparelhos.values():
                    try:
                        await ap.atualizar()
                        ap.falhas = 0
                    except Exception as e:
                        ap.falhas += 1
                        log.warning("[%s] sem resposta (%d): %s", ap.id, ap.falhas, e)
                        if ap.falhas == 3:
                            await fb(db.reference("gree/aparelhos/" + ap.id).update, {"online": False, "atualizado": agora()})
                        if ap.falhas >= 6:
                            raise RuntimeError("sessão perdida — vou entrar de novo")

        await asyncio.gather(consumir(), vigiar())
    finally:
        for ap in aparelhos.values():
            try:
                await ap.dev.close()
            except Exception:
                pass
        try:
            await disc.close()
        except Exception:
            pass


async def main():
    iniciar_firebase()
    loop = asyncio.get_running_loop()
    fila = asyncio.Queue()

    def ao_evento(ev):                                              # roda numa thread do firebase_admin
        for item in comandos_do_evento(ev.path, ev.data):
            loop.call_soon_threadsafe(fila.put_nowait, item)
    db.reference("gree/comandos").listen(ao_evento)

    espera = 5
    while True:                                                     # supervisor: cai → espera → entra de novo
        try:
            await sessao(fila)
        except Exception as e:
            log.error("Sessão encerrada: %s — nova tentativa em %ss", e, espera)
        await asyncio.sleep(espera)
        espera = min(espera * 2, 120)


if __name__ == "__main__":
    asyncio.run(main())
