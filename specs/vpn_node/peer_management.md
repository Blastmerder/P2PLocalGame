# Peer Management Specification

## Overview
Defines how the `VPNNode` tracks, discovers, and manages peer connections in the P2P network.

## Peer Representation
A peer is uniquely identified by its address tuple: `(host: str, port: int)`.

## Core Logic

### Peer Registration
- **`add_peer(peer: Peer)`**: Adds a new peer to the internal registry.
- **`_add_initial_peers()`**: Populates the peer registry using the configuration's list of predefined peers.

### Peer Discovery
- **Automatic Discovery**: When a valid UDP packet is received from an unknown address, a new `Peer` object is automatically created and added to the registry.

### Peer Lifecycle & Maintenance
- **Activity Tracking**: Every time a packet is received from a peer, the peer's internal "last seen" timestamp is updated (`peer.touch()`).
- **Pruning**:
    - During broadcasts, peers that are neither `is_alive()` nor `unconfirmed` (new/pending) are considered dead.
    - Dead peers are removed from the registry to prevent sending data to unreachable nodes.

### Peer Status Monitoring
- **`_log_peers()`**: Periodically logs statistics including:
    - `alive`: Peers that have responded and are confirmed.
    - `pending`: New peers that haven't yet responded to a `HELLO`.
    - `dead`: Peers that have timed out and are waiting for removal.
    - `total`: Total number of entries in the registry.
