# Packet Protocol Specification

## Overview
Defines the wire format for all communication between VPN nodes in the P2P network.

## Wire Format
All packets must follow the structure: `[ MAGIC (5 bytes) | TYPE (1 byte) | PAYLOAD ]`

### Header Components
- **MAGIC**: A constant byte sequence used to identify valid VPN packets.
- **TYPE**: A single byte indicating the purpose of the packet.

### Packet Types
| Type | Name | Description | Payload |
| :--- | :--- | :--- | :--- |
| `0x01` | `TYPE_DATA` | Raw Ethernet frame encapsulated for tunneling. | Raw Ethernet frame bytes. |
| `0x02` | `TYPE_HELLO` | Keepalive/Peer announcement packet. | None. |

## Functions
### `encode_data(frame: bytes) -> bytes`
- **Input**: Raw Ethernet frame bytes.
- **Output**: Encoded packet with `TYPE_DATA` and `MAGIC`.

### `decode(packet: bytes) -> (type: Optional[int], payload: Optional[bytes])`
- **Input**: Received UDP datagram.
- **Validation**:
    - Must be at least `MAGIC_LEN + 1` bytes.
    - Must start with the correct `MAGIC` sequence.
- **Output**: Returns the packet type and the payload if valid, otherwise `(None, None)`.
