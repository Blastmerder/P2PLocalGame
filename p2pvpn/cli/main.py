import argparse
import asyncio
import logging
import signal
import sys
import os
import platform
import ipaddress
from typing import Optional, List, Dict, Any

from p2pvpn.cli.config_builder import ConfigBuilder
from p2pvpn.core.engine import Engine
from p2pvpn.core.peer_manager import PeerManager
from p2pvpn.core.models.vpn_config import VPNConfig
from p2pvpn.transport.udp.udp_transport import UDPTransport
from p2pvpn.interface.tap.tap_interface import TAPInterface
from p2pvpn.core.utils import is_admin
from p2pvpn.transport.udp.stun import discover_async, STUNResult

# Set up logging
logger = logging.getLogger("p2pvpn.cli")

def check_privileges():
    """Checks for root/admin privileges."""
    if not is_admin():
        if platform.system() == "Windows":
            print("Error: This application must be run as Administrator (required for TAP-Windows6).")
        else:
            print("Error: This application must be run as root (sudo) to manage TAP interfaces.")
        sys.exit(1)

async def main_async(args: argparse.Namespace):
    # 1. Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    # 2. Check privileges
    check_privileges()

    # 3. Build Config
    # We need to identify which arguments were actually provided to avoid overriding JSON with argparse defaults.
    # We can do this by checking sys.argv.
    
    cli_overrides: Dict[str, Any] = {}
    
    # List of arguments that have defaults in argparse that we want to avoid overriding JSON with.
    # If they are NOT in sys.argv, we set them to None so ConfigBuilder ignores them.
    
    def is_provided(flag: str) -> bool:
        return flag in sys.argv

    # Mapping argparse destinations to ConfigBuilder keys
    # Note: for 'peer' and 'stun_server', they are lists.
    if is_provided("--ip"):
        cli_overrides["ip"] = args.ip
    if is_provided("--port"):
        cli_overrides["port"] = args.port
    if is_provided("--tap"):
        cli_overrides["tap"] = args.tap
    if is_provided("--prefix"):
        cli_overrides["prefix"] = args.prefix
    if is_provided("--peer"):
        cli_overrides["peer"] = args.peer
    if is_provided("--no-stun"):
        cli_overrides["no_stun"] = args.no_stun
    if is_provided("--stun-timeout"):
        cli_overrides["stun_timeout"] = args.stun_timeout
    if is_provided("--stun-server"):
        cli_overrides["stun_server"] = args.stun_server
    if is_provided("--mtu"):
        cli_overrides["mtu"] = args.mtu

    # Parse config file path
    config_path = args.config

    # Build the configuration object
    try:
        config: VPNConfig = ConfigBuilder.build(cli_overrides, config_path)
    except Exception as e:
        print(f"Configuration Error: {e}")
        sys.exit(1)

    # 4. Optional STUN discovery and Banner
    stun_result: Optional[STUNResult] = None
    if not config.skip_stun:
        logger.info("Performing STUN discovery...")
        try:
            # Use the listen port for STUN discovery to ensure NAT mapping is consistent
            stun_result = await discover_async(
                servers=[(s.host, s.port) for s in config.stun_servers] if config.stun_servers else None,
                timeout=config.stun_timeout,
                local_port=config.listen_port
            )
            logger.info("STUN discovery successful.")
        except Exception as e:
            logger.warning("STUN discovery failed: %s. Continuing without it.", e)

    # Print Banner
    pub_addr = f"{stun_result.public_ip}:{stun_result.public_port}" if stun_result else "unavailable"
    via = stun_result.server_used if stun_result else "—"
    print(f"\n  ╔══════════════════════════════════════╗")
    print(f"  ║         P2P L2 VPN  starting         ║")
    print(f"  ║  Public addr: {pub_addr:<23}║")
    print(f"  ║  STUN server: {via:<23}║")
    print(f"  ╚══════════════════════════════════════╝\n")
    if stun_result:
        print(f"  ► Share this address with peers:  {stun_result.public_ip}:{stun_result.public_port}\n")

    # 5. Initialize Components
    
    # Transport
    transport = UDPTransport()
    await transport.open(config.local_ip, config.listen_port)

    # Network Interface (TAP)
    # Need to compute netmask from prefix
    try:
        netmask = str(ipaddress.IPv4Network(f"{config.local_ip}/{config.prefix}", strict=False).netmask)
    except Exception as e:
        print(f"Error calculating netmask: {e}")
        sys.exit(1)
        
    network_interface = TAPInterface(
        device_name=config.tap_name,
        ip_address=config.local_ip,
        netmask=netmask,
        mtu=config.mtu
    )
    await network_interface.setup()

    # Peer Manager
    peer_manager = PeerManager()
    # Add initial peers from config
    for peer_info in config.peers:
        from p2pvpn.core.models.peer import Peer, PeerState
        new_peer = Peer(
            peer_id=f"{peer_info.host}:{peer_info.port}",
            address=peer_info.host,
            port=peer_info.port,
            state=PeerState.PENDING
        )
        peer_manager.add_peer(new_peer)

    # Engine
    engine = Engine(transport, network_interface, peer_manager, config)

    # 6. Signal Handling & Execution
    loop = asyncio.get_running_loop()

    def _shutdown():
        logger.info("Shutdown signal received. Cleaning up...")
        # Stop engine
        asyncio.create_task(engine.stop())
        # Teardown components
        asyncio.create_task(network_interface.teardown())
        asyncio.create_task(transport.close())

    if platform.system() != "Windows":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown()))

    try:
        await engine.run()
    except asyncio.CancelledError:
        logger.info("Engine execution cancelled.")
    except Exception as e:
        logger.error("Unexpected error during execution: %s", e, exc_info=True)
    finally:
        # Ensure cleanup happens
        logger.info("Finalizing shutdown...")
        # We should wait for the shutdown tasks to complete if possible, 
        # but since this is the end of main_async, we might just exit.
        # In a real app, you'd want a better way to wait for the cleanup.
        # For now, let's just try to do it.
        try:
            await network_interface.teardown()
            await transport.close()
        except Exception as e:
            logger.warning("Error during final cleanup: %s", e)

def main():
    parser = argparse.ArgumentParser(
        description="P2P L2 VPN — virtual LAN over UDP with hole punching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", metavar="FILE", help="Path to a JSON configuration file. Overrides all other flags.")
    parser.add_argument("--ip", default="10.0.0.1", help="Virtual IP address for this node.")
    parser.add_argument("--port", type=int, default=5555, help="UDP listen port.")
    parser.add_argument("--tap", default="tap0", help="Name of the TAP/TUN interface.")
    parser.add_argument("--prefix", type=int, default=24, help="Network prefix length.")
    parser.add_argument("--peer", action="append", metavar="HOST:PORT", help="Peer public address in HOST:PORT format. Can be repeated.")
    parser.add_argument("--no-stun", action="store_true", dest="no_stun", help="Skip STUN discovery.")
    parser.add_argument("--stun-server", action="append", metavar="HOST:PORT", dest="stun_server", help="Custom STUN server in HOST:PORT format. Can be repeated.")
    parser.add_argument("--stun-timeout", type=float, default=3.0, dest="stun_timeout", help="Timeout for STUN discovery in seconds.")
    parser.add_argument("--debug", action="store_true", help="Enable debug-level logging.")

    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        # On Windows, Ctrl-C might raise KeyboardInterrupt
        pass
    except Exception as e:
        print(f"Fatal Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
