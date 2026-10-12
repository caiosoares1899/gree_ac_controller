"""Tradução entre o vocabulário da página (strings: 'cool', 'high'…) e a biblioteca greeclimate-davo22 (inteiros/bools),
e leitura dos comandos que a página grava no Firebase. Sem dependência de rede nem da lib da Gree — testável sozinho."""

CAMPOS = ["power", "mode", "temperature", "fanSpeed", "turbo", "quiet", "lights", "swingVert"]

MODE = {0: "auto", 1: "cool", 2: "dry", 3: "fan_only", 4: "heat"}
FAN = {0: "auto", 1: "low", 2: "mediumLow", 3: "medium", 4: "mediumHigh", 5: "high"}
SWING = {0: "default", 1: "full", 2: "fixedTop", 3: "fixedMidTop", 4: "fixedMid", 5: "fixedMidBottom", 6: "fixedBottom"}
INV_MODE = {v: k for k, v in MODE.items()}
INV_FAN = {v: k for k, v in FAN.items()}
INV_SWING = {v: k for k, v in SWING.items()}

# o que a página pode pedir — qualquer outra coisa é descartada (o comando vem de um navegador)
PERMITIDO = {
    "power": {"on", "off"},
    "mode": set(INV_MODE),
    "fanSpeed": set(INV_FAN),
    "turbo": {"on", "off"},
    "quiet": {"off", "mode1", "mode2", "mode3"},
    "lights": {"on", "off"},
    "swingVert": set(INV_SWING),
}


def limpa_patch(cmd):
    out = {}
    t = cmd.get("temperature")
    if isinstance(t, int) and not isinstance(t, bool) and 16 <= t <= 30:
        out["temperature"] = t
    for k, ok in PERMITIDO.items():
        if cmd.get(k) in ok:
            out[k] = cmd[k]
    return out


def estado_de(dev):
    """Estado do aparelho no formato que a página lê."""
    quiet = int(getattr(dev, "quiet", 0) or 0)
    ct = getattr(dev, "current_temperature", None)
    return {
        "power": "on" if dev.power else "off",
        "mode": MODE.get(int(dev.mode), "auto"),
        "temperature": int(dev.target_temperature),
        "currentTemperature": ct if isinstance(ct, (int, float)) else None,
        "fanSpeed": FAN.get(int(dev.fan_speed), "auto"),
        "turbo": "on" if getattr(dev, "turbo", False) else "off",
        "quiet": "off" if quiet == 0 else "mode%d" % min(quiet, 3),
        "lights": "on" if getattr(dev, "light", False) else "off",
        "swingVert": SWING.get(int(getattr(dev, "vertical_swing", 0) or 0), "default"),
    }


def aplica_patch(dev, patch, Mode=int, FanSpeed=int, VerticalSwing=int):
    """Marca as mudanças no objeto do aparelho (a lib só envia no push_state_update)."""
    if "mode" in patch:
        dev.mode = Mode(INV_MODE[patch["mode"]])
    if "temperature" in patch:
        dev.target_temperature = patch["temperature"]
    if "fanSpeed" in patch:
        dev.fan_speed = FanSpeed(INV_FAN[patch["fanSpeed"]])
    if "swingVert" in patch:
        dev.vertical_swing = VerticalSwing(INV_SWING[patch["swingVert"]])
    if "turbo" in patch:
        dev.turbo = patch["turbo"] == "on"
    if "quiet" in patch:
        dev.quiet = patch["quiet"] != "off"
    if "lights" in patch:
        dev.light = patch["lights"] == "on"
    if "power" in patch:
        dev.power = patch["power"] == "on"


def comandos_do_evento(path, data):
    """Normaliza um evento do listener do Firebase em (aparelho, pushId, comando).
    O 1º evento traz tudo em '/', os seguintes chegam em '/{aparelho}/{pushId}'."""
    partes = [p for p in (path or "").split("/") if p]
    if not isinstance(data, dict):
        return
    if len(partes) == 0:
        for ap, pushes in data.items():
            if isinstance(pushes, dict):
                for pid, cmd in pushes.items():
                    if isinstance(cmd, dict):
                        yield ap, pid, cmd
    elif len(partes) == 1:
        for pid, cmd in data.items():
            if isinstance(cmd, dict):
                yield partes[0], pid, cmd
    elif len(partes) == 2:
        yield partes[0], partes[1], data
