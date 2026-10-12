# STUN Client Specification

## Summary
`stun_client.py` is a minimal STUN (Session Traversal Utilities for NAT) client implementing RFC 5389. It discovers a node's public IP address and port by sending a Binding Request to STUN servers. It supports multiple fallback servers, both asynchronous and synchronous interfaces, and handles both `MAPPED-ADDRESS` and `XOR-MAPPED-ADDRESS` attributes.

## Business Logics

### 1. Packet Construction (`_build_binding_request`)
- **Goal**: Create a valid STUN Binding Request packet.
- **Logic**:
    - Generates a 12-byte random transaction ID.
    - Packs a header containing:
        - Message Type: `BINDING_REQUEST` (0x0001).
        - Message Length: 0.
        - Magic Cookie: `STUN_MAGIC_COOKIE` (0x2112A442).
        - Transaction ID.
- **Output**: A tuple of `(packet_bytes, transaction_id)`.

### 2. Response Parsing (`_parse_response`, `_parse_xor_mapped`, `_parse_mapped`)
- **Goal**: Extract the public IP and port from a STUN Binding Response.
- **Logic**:
    - **Header Validation**: Checks if the response is long enough, has the correct message type (`BINDING_RESPONSE`), matches the `STUN_MAGIC_COOKIE`, and has a matching transaction ID.
    - **Attribute Iteration**: Iterates through the STUN attributes in the payload.
    - **Attribute Handling**:
        - **XOR-MAPPED-ADDRESS**: Decodes the XOR-obfuscated IP and port using the magic cookie. This is the preferred method (RFC 5389).
        - **MAPPED-ADDRESS**: Decodes the legacy plain-text IP and port.
    - **Preference**: Returns the `XOR-MAPPED-ADDRESS` result if available; otherwise, returns the `MAPPED-ADDRESS` result.
- **Output**: A tuple of `(ip_address_str, port_int)` or `None` on failure.

### 3. Async Network Protocol (`_STUNProtocol`)
- **Goal**: Manage the UDP lifecycle for asynchronous STUN requests.
- **Logic**:
    - Implements `asyncio.DatagramProtocol`.
    - **`datagram_received`**: Passes received data to the parser and resolves the `asyncio.Future` with the result or raises an exception.
    - **`error_received`**: Handles transport-level errors by setting an exception on the future.
    - **`connection_lost`**: Handles connection loss by setting a `ConnectionError`.

### 4. Public IP Discovery (`discover_async`, `discover`)
- **Goal**: Orchestrate the discovery process using a list of servers.
- **Logic**:
    - **Fallback Mechanism**: Iterates through the provided list of STUN servers.
    - **DNS Resolution**: Resolves the server hostname to an IP address.
    - **Socket Management**:
        - Creates a UDP socket with `SO_REUSEADDR` (and `SO_REUSEPORT` if available) to allow binding to the same port immediately after closing.
        - Binds to the specified `local_port` or an auto-selected port.
    - **Request Execution**: Sends the binding request via the `_STUNProtocol` and waits for a response with a specified timeout.
    - **Error Handling**: If a server fails or times out, it moves to the next server. If all servers fail, it raises a `RuntimeError`.
- **Output**: A `STUNResult` object containing `public_ip`, `public_port`, and `server_used`.
