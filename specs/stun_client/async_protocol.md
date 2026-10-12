# Specification: Async Network Protocol

## Logic: `_STUNProtocol`

### Description
Implements the `asyncio.DatagramProtocol` to handle asynchronous UDP communication for STUN requests.

### Requirements
- **`datagram_received(data, addr)`**:
    - Should not execute if the linked `asyncio.Future` is already completed.
    - Should call the response parser with the received `data` and the stored `txn_id`.
    - If parsing is successful, resolve the `Future` with the resulting `(ip, port)`.
    - If parsing fails, set a `ValueError("Invalid STUN response")` on the `Future`.
- **`error_received(exc)`**:
    - Set the received exception on the `Future` if it is not yet completed.
- **`connection_lost(exc)`**:
    - Set a `ConnectionError("STUN connection lost")` on the `Future` if it is not yet completed.

### Inputs
- `txn_id`: The 12-byte transaction ID used for the request.
- `future`: The `asyncio.Future` object to be resolved upon response or error.
