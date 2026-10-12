# Specification: Packet Construction

## Logic: `_build_binding_request`

### Description
Constructs a STUN Binding Request packet as per RFC 5389 to initiate the discovery of a public IP and port.

### Requirements
- Generate a unique 12-byte transaction ID (random bytes).
- Construct a header with the following fields (Big-endian):
    - Message Type (2 bytes): `BINDING_REQUEST` (0x0001).
    - Message Length (2 bytes): 0 (since there are no attributes in a request).
    - Magic Cookie (4 bytes): `0x2112A442`.
    - Transaction ID (12 bytes): The generated random bytes.

### Inputs
- None.

### Outputs
- `tuple[bytes, bytes]`: Returns a tuple containing the raw packet bytes and the transaction ID used.
