# Specification: Public IP Discovery

## Logic: `discover_async`, `discover`

### Description
Orchestrates the process of discovering the public IP address and port by communicating with one or more STUN servers.

### Requirements
- **Server Iteration**: Iterate through the provided list of STUN servers (or the `DEFAULT_SERVERS` if none are provided).
- **DNS Resolution**: For each server, resolve the hostname to an IPv4 address using `loop.getaddrinfo`.
- **Socket Setup**:
    - Create a UDP socket (`AF_INET`, `SOCK_DGRAM`).
    - Set `SO_REUSEADDR` to 1.
    - Set `SO_REUSEPORT` to 1 if available and successfully.
    - Bind the socket to `0.0.0.0` and the specified `local_port` (or 0 for auto-assignment).
- **Communication**:
    - Use `loop.create_datagram_endpoint` with `_STUNProtocol`.
    - Send the `Binding Request` to the resolved server address.
    - Wait for the `Future` to be resolved or for a `timeout` to occur.
- **Cleanup**: Ensure the transport is closed in the `finally` block after each attempt.
- **Fallback Mechanism**: If a server fails (timeout, error, or invalid response), log the error and attempt the next server in the list.
- **Success**: Return a `STUNResult` containing the discovered `public_ip`, `public_port`, and `server_used`.
- **Failure**: If all servers in the list are exhausted without success, raise a `RuntimeError` containing the last encountered error.

### Inputs
- `servers`: `Optional[list[tuple[str, int]]]` - A list of (host, port) tuples.
- `timeout`: `float` - Timeout in seconds for each individual server attempt.
- `local_port`: `int` - The local UDP port to bind to.

### Outputs
- `STUNResult`: An object containing:
    - `public_ip`: The discovered public IP (string).
    - `public_port`: The discovered public port (int).
    - `server_used`: The server that successfully provided the info (string).
- `RuntimeError`: Raised if all servers fail.
