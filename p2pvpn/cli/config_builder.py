import json
import ipaddress
from typing import Any, Dict, List, Optional

from p2pvpn.core.models.vpn_config import VPNConfig, PeerInfo, StunServerInfo

class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass

class ConfigBuilder:
    """
    Builder for VPNConfig that merges JSON configuration and command-line arguments.
    """

    @staticmethod
    def build(cli_overrides: Dict[str, Any], json_config_path: Optional[str] = None) -> VPNConfig:
        """
        Builds a validated VPNConfig by merging JSON and CLI overrides.
        CLI overrides take precedence over JSON configuration.
        
        Args:
            cli_overrides: A dictionary of command-line arguments that should override 
                           the JSON configuration. Values should be None if not provided.
            json_config_path: Path to the JSON configuration file.

        Returns:
            A validated VPNConfig object.
        """
        config_dict = {}

        # 1. Load JSON configuration if provided
        if json_config_path:
            try:
                with open(json_config_path, 'r') as f:
                    config_dict = json.load(f)
            except Exception as e:
                raise ConfigValidationError(f"Failed to load JSON config: {e}")

        # 2. Merge CLI overrides
        # Mapping of cli_arg_name -> config_key
        mapping = {
            "ip": "local_ip",
            "port": "listen_port",
            "tap": "tap_name",
            "prefix": "prefix",
            "peer": "peers",
            "no_stun": "skip_stun",
            "stun_timeout": "stun_timeout",
            "stun_server": "stun_servers",
            "mtu": "mtu",
        }

        for arg_name, config_key in mapping.items():
            if arg_name in cli_overrides:
                val = cli_overrides[arg_name]
                
                # Only override if the value is provided (not None)
                if val is None:
                    continue

                if config_key == "peers":
                    # val is expected to be a list of "host:port" strings
                    peers = []
                    for p in val:
                        try:
                            if isinstance(p, dict):
                                peers.append(p)
                            else:
                                host, port_str = p.rsplit(":", 1)
                                peers.append({"host": host, "port": int(port_str)})
                        except (ValueError, AttributeError):
                            raise ConfigValidationError(f"Invalid peer format: {p}")
                    config_dict[config_key] = peers
                elif config_key == "stun_servers":
                    # val is expected to be a list of "host:port" strings
                    servers = []
                    for s in val:
                        try:
                            if isinstance(s, dict):
                                servers.append(s)
                            else:
                                host, port_str = s.rsplit(":", 1)
                                servers.append({"host": host, "port": int(port_str)})
                        except (ValueError, AttributeError):
                            raise ConfigValidationError(f"Invalid stun server format: {s}")
                    config_dict[config_key] = servers
                else:
                    config_dict[config_key] = val

        # 3. Validation
        ConfigBuilder._validate(config_dict)

        # 4. Return VPNConfig object
        return VPNConfig.from_dict(config_dict)

    @staticmethod
    def _validate(config: Dict[str, Any]) -> None:
        """
        Validates the configuration dictionary.
        """
        # Validate IP address
        if "local_ip" in config:
            try:
                ipaddress.ip_address(config["local_ip"])
            except ValueError:
                raise ConfigValidationError(f"Invalid local_ip: {config['local_ip']}")

        # Validate ports
        if "listen_port" in config:
            port = config["listen_port"]
            if not (0 <= port <= 65535):
                raise ConfigValidationError(f"Invalid listen_port: {port}")

        # Validate prefix
        if "prefix" in config:
            prefix = config["prefix"]
            if not (0 <= prefix <= 32):
                raise ConfigValidationError(f"Invalid prefix: {prefix}")

        # Validate peers
        if "peers" in config:
            for peer in config["peers"]:
                if "host" not in peer or "port" not in peer:
                    raise ConfigValidationError("Peer must have host and port")
                try:
                    # Allow hostnames for peers, but check port
                    pass
                except Exception:
                    pass
                if not (0 <= peer["port"] <= 65535):
                    raise ConfigValidationError(f"Invalid peer port: {peer['port']}")

        # Validate stun_servers
        if "stun_servers" in config:
            for server in config["stun_servers"]:
                if "host" not in server or "port" not in server:
                    raise ConfigValidationError("Stun server must have host and port")
                if not (0 <= server["port"] <= 65535):
                    raise ConfigValidationError(f"Invalid stun server port: {server['port']}")

        # Validate mtu
        if "mtu" in config:
            if not (576 <= config["mtu"] <= 9000):
                raise ConfigValidationError(f"Invalid MTU: {config['mtu']}")
