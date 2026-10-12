# Data Forwarding Specification

## Overview
Describes the mechanism for bridging local Ethernet traffic (via TAP/TUN interface) to the remote P2P network and vice versa.

## Traffic Flows

### 1. Local TAP → Remote Peers (Outbound)
When the local operating system sends an Ethernet frame through the virtual TAP interface:
- **Trigger**: `_on_tap_frame(frame: bytes)` is called.
- **Encapsulation**: The frame is wrapped in a VPN packet with `TYPE_DATA`.
- **Transmission**: The encapsulated packet is broadcast to all reachable peers via `_broadcast(frame)`.
- **Peer Filtering**: 
    - Data is sent to all `is_alive()` peers.
    - Data is also sent to "pending" peers (those not yet `confirmed`) to ensure they receive traffic upon connection.

### 2. Remote Peers → Local TAP (Inbound)
When a UDP datagram is received from a peer:
- **Trigger**: `_on_udp(data: bytes, addr: tuple)` is called.
- **Decapsulation**: The payload is extracted from the VPN packet.
- **Verification**: The packet type must be `TYPE_DATA`.
- **Injection**: The raw Ethernet payload is written directly to the local TAP device via `_tap.write(payload)`, making it available to the local network stack.
