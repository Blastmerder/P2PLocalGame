# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────
ETH_PROTO_ARP = 0x0806

MAGIC       = b"P2PL2"  # 5-byte header prefix to identify our packets
MAGIC_LEN   = len(MAGIC)
HEARTBEAT_INTERVAL  = 5   # seconds between regular keepalive pings
PEER_TIMEOUT        = 30  # seconds before a peer is considered dead
PUNCH_COUNT         = 10  # rapid HELLOs at startup for hole punching
PUNCH_INTERVAL      = 0.3 # seconds between punch packets

# ── MTU budget ────────────────────────────────────────────────
# Physical MTU 1500
#  - IP header   20
#  - UDP header   8
#  - MAGIC+TYPE   6
#  - PPPoE/ISP   46  (safety margin)
# ─────────────────
# TAP MTU       1420  → Ethernet frames never exceed physical MTU,
#                       NAT routers won't fragment/drop UDP datagrams
TAP_MTU = 1420
