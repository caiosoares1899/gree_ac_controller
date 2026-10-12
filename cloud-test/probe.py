"""Teste SOMENTE LEITURA da nuvem da Gree: entra, lista os aparelhos da conta e lê o estado de cada um.
Não envia nenhum comando e não imprime a chave de criptografia.

Uso (ex.: no Google Colab):
    !pip install -q "greeclimate-davo22 @ git+https://github.com/davo22/greeclimate.git@2.3.0"
    GREE_USER=... GREE_PASS=... GREE_SERVER="South American" python probe.py
Use GREE_SERVER=all pra tentar todas as regiões, ou GREE_SERVER=list pra ver os nomes válidos.
"""
import asyncio
import os
import sys

from greeclimate_davo22.cloud_discovery import CloudDiscovery

USER = os.environ.get("GREE_USER", "")
PASS = os.environ.get("GREE_PASS", "")
SERVER = os.environ.get("GREE_SERVER", "South American")


async def main():
    if SERVER == "list":
        print("Regiões válidas:", CloudDiscovery.list_servers())
        return
    if not USER or not PASS:
        sys.exit("Defina GREE_USER e GREE_PASS.")

    # GREE_SERVER=all  -> tenta cada região até uma aceitar o login (a conta só existe numa delas)
    servidores = list(CloudDiscovery.list_servers()) if SERVER == "all" else [SERVER]
    disc, devices, usado = None, None, None
    for srv in servidores:
        d_try = CloudDiscovery(username=USER, password=PASS, server=srv)
        try:
            devices = await d_try.scan()
            disc, usado = d_try, srv
            break
        except Exception as e:
            print(f"[{srv}] não entrou: {e}")
            try:
                await d_try.close()
            except Exception:
                pass
    if disc is None:
        sys.exit("\nNenhuma região aceitou o login. Confira e-mail/senha e se a conta tem senha (login só com Google/Apple não tem).")
    try:
        print(f"\nEntrou na região: {usado}")
        print(f"\nAparelhos na conta ({usado}): {len(devices)}")
        for d in devices:
            print(f"  - {d.name} | mac={d.mac} | online={d.online} | modelo={d.model} | versão={d.version}")

        for d in devices:
            for cipher in (1, 2):          # 1 = AES-ECB (a maioria), 2 = AES-GCM (módulos novos)
                dev = None
                try:
                    dev = await disc.create_device(d, cipher_version=cipher)
                    await dev.bind()
                    await dev.update_state()
                    print(f"\n[{d.name}] cifra v{cipher} OK ->",
                          {k: getattr(dev, k, None) for k in
                           ("power", "mode", "target_temperature", "current_temperature", "fan_speed")})
                    break
                except Exception as e:                       # tenta a outra cifra
                    print(f"[{d.name}] cifra v{cipher} falhou: {type(e).__name__}: {e}")
                finally:
                    if dev is not None:
                        try:
                            await dev.close()
                        except Exception:
                            pass
    finally:
        await disc.close()


asyncio.run(main())
