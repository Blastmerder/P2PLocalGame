# Specification: Response Parsing

## Logic: `_parse_response`, `_parse_xor_mapped`, `_parse_mapped`

### Description
Decodes a STUN Binding Response packet to extract the node's public IP address and port.

### Requirements
- **Header Validation**:
    - Total length must be at least `HEADER_SIZE` (20 bytes).
    - Message Type must be `BINDING_RESPONSE` (0x0101).
    - Magic Cookie must be `0x2112A442`.
    - Transaction ID must match the ID sent in the request.
    - Handle `BINDING_ERROR` type by returning `None`.
- **Attribute Parsing**:
    - Iterate through attributes using (Type, Length) pairs.
    - Handle padding to 4-byte boundaries.
- **Address Decoding**:
    - **`XOR-MAPPED-ADDRESS`** (0x0020):
        - Extract Family (1 byte).
        - Decode Port (2 bytes) by XORing with `(STUN_MAGIC_COOKIE >> 16)`.
        - If IPv4: Decode IP (4 bytes) by XORing with `STUN_MAGIC_COOKIE`.
    - **`MAPPED-ADDRESS`** (0x0001):
        - Extract Family (1 byte).
        - Extract Port (2 bytes).
        - If IPv4: Extract IP (4 bytes).
- **Priority**: Prefer `XOR-MAPPED-ADDRESS` over `MAPPED-ADDRESS`.

### Inputs
- `data`: The raw bytes received from the STUN server.
- `txn_id`: The transaction ID sent in the original request.

### Outputs
- `Optional[tuple[str, int]]`: Returns `(public_ip, public_port)` if valid, otherwise `None`.
