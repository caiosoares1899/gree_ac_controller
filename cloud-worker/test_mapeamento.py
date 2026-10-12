"""Roda com:  python test_mapeamento.py   (sem rede, sem a lib da Gree)."""
from types import SimpleNamespace as NS

from mapeamento import aplica_patch, comandos_do_evento, estado_de, limpa_patch


def teste_limpa():
    assert limpa_patch({"temperature": 24, "power": "on", "x": 1}) == {"temperature": 24, "power": "on"}
    assert limpa_patch({"temperature": 99}) == {}
    assert limpa_patch({"temperature": True}) == {}
    assert limpa_patch({"mode": "heat", "fanSpeed": "evil"}) == {"mode": "heat"}


def teste_estado():
    dev = NS(power=True, mode=1, target_temperature=16, current_temperature=25, fan_speed=5,
             turbo=False, quiet=0, light=True, vertical_swing=1)
    assert estado_de(dev) == {
        "power": "on", "mode": "cool", "temperature": 16, "currentTemperature": 25, "fanSpeed": "high",
        "turbo": "off", "quiet": "off", "lights": "on", "swingVert": "full"}


def teste_aplica():
    dev = NS()
    aplica_patch(dev, {"mode": "heat", "temperature": 22, "fanSpeed": "low", "swingVert": "fixedBottom",
                       "turbo": "on", "quiet": "off", "lights": "off", "power": "off"})
    assert (dev.mode, dev.target_temperature, dev.fan_speed, dev.vertical_swing) == (4, 22, 1, 6)
    assert dev.turbo is True and dev.quiet is False and dev.light is False and dev.power is False


def teste_eventos():
    cmd = {"power": "on", "ts": 1}
    assert list(comandos_do_evento("/", {"quarto": {"p1": cmd}})) == [("quarto", "p1", cmd)]
    assert list(comandos_do_evento("/quarto", {"p1": cmd})) == [("quarto", "p1", cmd)]
    assert list(comandos_do_evento("/quarto/p1", cmd)) == [("quarto", "p1", cmd)]
    assert list(comandos_do_evento("/quarto/p1", None)) == []            # remoção
    assert list(comandos_do_evento("/quarto/p1/power", "on")) == []      # campo solto


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("teste_"):
            fn()
            print("ok", nome)
