#!/usr/bin/env python3
"""
p2pvpn — command-line entry point.

Usage examples
──────────────
  # Node A (IP 10.0.0.1, listens on UDP 5555, connects to B at 5.6.7.8:5555)
  sudo python3 main.py --ip 10.0.0.1 --port 5555 --peer 5.6.7.8:5555

  # Node B (IP 10.0.0.2, listens on UDP 5555)
  sudo python3 main.py --ip 10.0.0.2 --port 5555 --peer <A_public_ip>:5555

  # Using a config file instead
  sudo python3 main.py --config node_a.json

  # Skip STUN (local network, both on same LAN)
  sudo python3 main.py --ip 10.0.0.1 --port 5555 --peer 192.168.1.5:5555 --no-stun
"""

import argparse
import asyncio
import json
import logging
import signal
import sys
from typing import Optional

from vpn_node import VPNNode
from stun_client import discover_async, STUNResult
from tap import is_admin, TAPDevice
from constants import *

log = logging.getLogger("vpn.main")

logging.basicConfig(
    filename='logs.log',
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def parse_peer(s: str) -> dict:
    parts = s.rsplit(":", 1)
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"Peer must be host:port, got: {s!r}")
    return {"host": parts[0], "port": int(parts[1])}


def build_config(args) -> dict:
    if args.config:
        with open(args.config) as f:
            cfg = json.load(f)
        log.info("Loaded config from %s", args.config)
    else:
        cfg = {
            "local_ip":    args.ip,
            "listen_port": args.port,
            "tap_name":    args.tap,
            "prefix":      args.prefix,
            "peers":       [parse_peer(p) for p in (args.peer or [])],
        }
    return cfg


def check_privileges():
    """Требуется root на Linux / Administrator на Windows — для TAP."""
    if not is_admin():
        if sys.platform == "win32":
            sys.exit("Error: must run as Administrator "
                     "(TAP-Windows6 requires admin rights).")
        sys.exit("Error: must run as root (TAP interface requires root).")


# ──────────────────────────────────────────────────────────────
# STUN
# ──────────────────────────────────────────────────────────────

async def run_stun(cfg: dict) -> Optional[STUNResult]:
    """
    Определить публичный IP:port через STUN.

    КРИТИЧНО: биндим STUN-сокет на тот же порт что будет слушать VPN.
    NAT создаёт отдельный маппинг для каждого (src_port, dst) —
    если STUN использует порт 0, NAT назначит другой внешний порт.
    Пиру нужно сообщать именно порт соответствующий listen_port.
    STUN-сокет закрывается до старта VPN, порт освобождается мгновенно.
    """
    if cfg.get("skip_stun"):
        return None

    stun_servers = None
    if cfg.get("stun_servers"):
        stun_servers = [(s["host"], s["port"]) for s in cfg["stun_servers"]]

    listen_port = cfg.get("listen_port", 5555)
    log.info("Running STUN discovery on port %d…", listen_port)
    try:
        result = await discover_async(
            servers=stun_servers,
            timeout=cfg.get("stun_timeout", 3.0),
            local_port=listen_port,
        )
        cfg["stun"] = {"ip": result.public_ip, "port": result.public_port}
        return result
    except RuntimeError as e:
        log.warning("STUN discovery failed (continuing anyway): %s", e)
        return None


# ──────────────────────────────────────────────────────────────
# Main async entry
# ──────────────────────────────────────────────────────────────

async def main_async(cfg: dict):
    stun = await run_stun(cfg)

    # Баннер
    pub_addr = f"{stun.public_ip}:{stun.public_port}" if stun else "unavailable"
    via      = stun.server_used if stun else "—"
    print(f"  ║  Public addr: {pub_addr:<23}║")
    print(f"  ║  STUN server: {via:<23}║")
    print( "  ╚══════════════════════════════════════╝\n")
    if stun:
        print(f"  ► Share this address with peers:  {stun.public_ip}:{stun.public_port}\n")
    tap = TAPDevice(
            name=cfg.get("tap_name", "tap0"),
            ip=cfg["local_ip"],
            prefix=cfg.get("prefix", 24),
            mtu=cfg.get("mtu", TAP_MTU),
        )
    node = VPNNode(cfg, tap)

    loop = asyncio.get_running_loop()

    def _shutdown():
        log.info("Shutting down…")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    # add_signal_handler не поддерживается в ProactorEventLoop на Windows,
    # но там Ctrl-C всё равно прилетает как KeyboardInterrupt в asyncio.run —
    # обрабатываем его в main().
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT,  _shutdown)
        loop.add_signal_handler(signal.SIGTERM, _shutdown)

    try:
        tap.setup()
        await node.run()
        
    except asyncio.CancelledError:
        log.info("Node stopped.")


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="P2P L2 VPN — virtual LAN over UDP with hole punching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--config",  metavar="FILE",
                        help="JSON config file (overrides all other flags)")
    parser.add_argument("--ip",      default="10.0.0.1",
                        help="Virtual IP for this node (default: 10.0.0.1)")
    parser.add_argument("--port",    type=int, default=5555,
                        help="UDP listen port (default: 5555)")
    parser.add_argument("--tap",     default="tap0",
                        help="TAP interface name (default: tap0)")
    parser.add_argument("--prefix",  type=int, default=24,
                        help="Network prefix length (default: 24)")
    parser.add_argument("--peer",    action="append", metavar="HOST:PORT",
                        help="Peer public address (repeat for N peers)")
    parser.add_argument("--no-stun", action="store_true", dest="no_stun",
                        help="Skip STUN (useful on LAN without NAT)")
    parser.add_argument("--stun-server", action="append", metavar="HOST:PORT",
                        dest="stun_server",
                        help="Custom STUN server (repeat for multiple)")
    parser.add_argument("--stun-timeout", type=float, default=3.0,
                        dest="stun_timeout",
                        help="STUN per-server timeout seconds (default: 3)")
    parser.add_argument("--debug",   action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    check_privileges()
    cfg = build_config(args)
    cfg["skip_stun"]    = args.no_stun
    cfg["stun_timeout"] = args.stun_timeout
    if args.stun_server:
        cfg["stun_servers"] = [
            {"host": h, "port": int(p)}
            for s in args.stun_server
            for h, p in [s.rsplit(":", 1)]
        ]

    print(f"""
  ╔══════════════════════════════════════╗
  ║         P2P L2 VPN  starting         ║
  ║  Virtual IP : {cfg['local_ip']:<22} ║
  ║  UDP Port   : {cfg['listen_port']:<22} ║
  ║  TAP Iface  : {cfg.get('tap_name','tap0'):<22} ║
  ║  Peers      : {len(cfg.get('peers',[])):<22} ║""")

    try:
        asyncio.run(main_async(cfg))
    except KeyboardInterrupt:
        # На Windows Ctrl-C прилетает сюда вместо signal handler'а
        log.info("Interrupted by user.")


if __name__ == "__main__":
    main()
