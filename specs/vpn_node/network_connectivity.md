# Network Connectivity Specification

## Overview
Defines the mechanisms used to establish connections, maintain them, and bypass NAT/firewalls in the P2P network.

## Connectivity Mechanisms

### 1. Hole Punching (NAT Traversal)
To establish communication through NAT/firewalls:
- **`_hole_punch_all()`**: Initiated at startup.
- **Procedure**:
    - The node sends a sequence of `HELLO` packets (`PUNCH_COUNT` times) to all known peers.
    - Each `HELLO` packet is sent at a specified `PUNCH_INTERVAL`.
- **Success Criterion**: A peer is considered "confirmed" once it responds to a `HELLO` packet, indicating an open communication path.

### 2. Heartbeat (Keepalive)
To maintain existing NAT mappings and detect peer availability:
- **`_heartbeat()`**: An asynchronous loop running for the lifetime of the node.
- **Procedure**:
    - Periodically (every `HEARTBEAT_INTERVAL`) sends a `HELLO` packet to all known peers.
    - This ensures that routers/firewalls do not close the UDP "session" due to inactivity.

### 3. Socket Management
- **Socket Configuration**: Uses a custom UDP socket created via `_make_udp_socket`.
- **Port Reuse**: Specifically configured with `SO_REUSEADDR` (and `SO_REUSEPORT` on Linux) to ensure that the local port can be quickly rebound even if the previous transport hasn't fully released it, preventing `WSAEADDRINUSE` errors.
