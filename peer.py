from typing import Dict, Optional

# ──────────────────────────────────────────────────────────────
# Peer state
# ──────────────────────────────────────────────────────────────
@dataclass
class Peer:
    host: str
    port: int
    # 0.0 = "никогда не отвечал" (пир из конфига, непроверенный)
    last_seen: float = 0.0
    mac: Optional[bytes] = None

    @property
    def addr(self):
        return (self.host, self.port)

    @property
    def confirmed(self) -> bool:
        """True если пир хотя бы раз прислал пакет."""
        return self.last_seen > 0.0

    def touch(self):
        self.last_seen = time.time()

    def is_alive(self) -> bool:
        """
        Живым считается только подтверждённый пир, от которого
        пришёл пакет не позже PEER_TIMEOUT секунд назад.
        Непроверенные пиры из конфига — статус 'pending', не alive.
        """
        if not self.confirmed:
            return False
        return (time.time() - self.last_seen) < PEER_TIMEOUT

    @property
    def status(self) -> str:
        if not self.confirmed:
            return "pending"
        return "alive" if self.is_alive() else "dead"

    def __str__(self):
        mac_str = ":".join(f"{b:02x}" for b in self.mac) if self.mac else "unknown"
        return f"{self.host}:{self.port} [{self.status}] mac={mac_str}"



