"""Roda com:  python test_sessao.py   (sem rede, sem a lib da Gree, sem Firebase — tudo simulado).
Prova que o serviço percebe uma conexão morta e reconecta, e que refaz o comando depois."""
import asyncio
import os
import sys
import types

os.environ.update(GREE_USER="x", GREE_PASS="x", FIREBASE_DB_URL="http://x")

# ---- dublês dos módulos externos (importados por main.py) ----
fa = types.ModuleType("firebase_admin")
fa.credentials = types.SimpleNamespace(Certificate=lambda *a, **k: None)
GRAVADO = []                                                       # tudo que o serviço "escreveria" no Firebase


class Ref:
    def __init__(self, path): self.path = path
    def update(self, v): GRAVADO.append(("update", self.path, v))
    def set(self, v): GRAVADO.append(("set", self.path, v))
    def push(self, v): GRAVADO.append(("push", self.path, v))
    def delete(self): GRAVADO.append(("delete", self.path, None))


fa.db = types.SimpleNamespace(reference=lambda p="": Ref(p))
fa.initialize_app = lambda *a, **k: None
sys.modules["firebase_admin"] = fa
cd = types.ModuleType("greeclimate_davo22.cloud_discovery")
dv = types.ModuleType("greeclimate_davo22.device")
dv.FanSpeed = dv.Mode = dv.VerticalSwing = int
pkg = types.ModuleType("greeclimate_davo22")


class Dev:
    """Aparelho falso. vivo=False imita a conexão MQTT morta: nenhuma resposta chega, e a lib não reclama."""
    def __init__(self, vivo):
        self.vivo = vivo
        self.power, self.mode, self.target_temperature, self.current_temperature = True, 1, 24, 26
        self.fan_speed, self.turbo, self.quiet, self.light, self.vertical_swing = 0, False, 0, True, 1
        self.enviados = []
    async def bind(self): pass
    async def close(self): pass
    def handle_state_update(self, **kw): pass
    async def update_state(self):
        if self.vivo: self.handle_state_update(Pow=1)
    async def push_state_update(self): self.enviados.append(self.target_temperature)


class Disc:
    vivo = True
    def __init__(self, **k): pass
    async def scan(self): return [types.SimpleNamespace(name="AC167f", mac="9424b8ab167f", online=True)]
    async def create_device(self, info, cipher_version=1): return Dev(Disc.vivo)
    async def close(self): pass


cd.CloudDiscovery = Disc
sys.modules.update({"greeclimate_davo22": pkg, "greeclimate_davo22.cloud_discovery": cd, "greeclimate_davo22.device": dv})

import main  # noqa: E402

main.POLL = 0.02
main.LIMITE_ONLINE_MS, main.LIMITE_RECONECTAR_MS = 150, 400
main.SOMENTE_LEITURA = False


async def cenario_morta():
    """Conexão morta + um comando: tem que (1) levantar SessaoPerdida, (2) devolver o comando à fila UMA vez, (3) marcar falha no status."""
    Disc.vivo = False
    fila = asyncio.Queue()
    fila.put_nowait(("quarto167f" if False else "ac167f", "p1", {"temperature": 23, "ts": main.agora(), "quem": "Caio", "uid": "u"}))
    try:
        await asyncio.wait_for(main.sessao(fila), 3)
        raise AssertionError("devia ter levantado SessaoPerdida")
    except main.SessaoPerdida:
        pass
    assert fila.qsize() == 1, "o comando devia voltar pra fila"
    _, _, cmd = fila.get_nowait()
    assert cmd["_t"] == 1, cmd
    st = [g for g in GRAVADO if g[1] == "gree/status/ultimoComando"]
    assert st and st[-1][2]["ok"] is False, st
    assert any(g[1] == "gree/aparelhos/ac167f" and g[2].get("online") is False for g in GRAVADO), "devia marcar offline"


async def cenario_viva():
    """Conexão viva: o comando é aplicado e o status fica ok."""
    Disc.vivo = True
    GRAVADO.clear()
    fila = asyncio.Queue()
    fila.put_nowait(("ac167f", "p2", {"temperature": 22, "ts": main.agora(), "quem": "Caio", "uid": "u"}))
    try:
        await asyncio.wait_for(main.sessao(fila), 0.6)
    except asyncio.TimeoutError:
        pass                                                       # sessão boa fica rodando pra sempre: o timeout é o esperado
    st = [g for g in GRAVADO if g[1] == "gree/status/ultimoComando"]
    assert st and st[-1][2]["ok"] is True, st
    assert fila.empty()


async def cenario_sessao_nao_vaza():
    """Depois que a sessão cai, não pode sobrar tarefa rodando (o código antigo usava gather e deixava vazar)."""
    antes = len(asyncio.all_tasks())
    Disc.vivo = False
    try:
        await asyncio.wait_for(main.sessao(asyncio.Queue()), 3)
    except main.SessaoPerdida:
        pass
    await asyncio.sleep(0.05)
    assert len(asyncio.all_tasks()) <= antes, asyncio.all_tasks()


async def tudo():
    await cenario_morta(); print("ok conexão morta → reconecta e refaz o comando")
    await cenario_viva(); print("ok conexão viva → comando aplicado")
    await cenario_sessao_nao_vaza(); print("ok sem tarefas vazando")


asyncio.run(tudo())
