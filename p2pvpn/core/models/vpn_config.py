from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class PeerInfo:
    host: str
    port: int

@dataclass(frozen=True)
class StunServerInfo:
    host: str
    port: int

@dataclass(frozen=True)
class VPNConfig:
    local_ip: str
    listen_port: int
    tap_name: str
    prefix: int
    peers: List[PeerInfo] = field(default_factory=list)
    skip_stun: bool = False
    stun_timeout: float = 3.0
    stun_servers: List[StunServerInfo] = field(default_factory=list)
    mtu: int = 1500
    keepalive_interval: int = 30
    connection_timeout: int = 10

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'VPNConfig':
        """
        Creates a VPNConfig object from a dictionary.
        Handles conversion of nested dictionaries to PeerInfo and StunServerInfo objects.
        """
        processed_dict = config_dict.copy()

        if "peers" in processed_dict and isinstance(processed_dict["peers"], list):
            processed_dict["peers"] = [
                PeerInfo(host=p["host"], port=p["port"])
                if isinstance(p, dict) else p
                for p in processed_dict["peers"]
            ]

        if "stun_servers" in processed_dict and isinstance(processed_dict["stun_servers"], list):
            processed_dict["stun_servers"] = [
                StunServerInfo(host=s["host"], port=s["port"])
                if isinstance(s, dict) else s
                for s in processed_dict["stun_servers"]
            ]

        return cls(**processed_dict)
