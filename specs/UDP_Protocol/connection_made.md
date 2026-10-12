# Logic: UDP Socket Initialization

## Description
When the UDP transport is established, the protocol initializes the node's transport property.

## Input
- `transport`: The asyncio transport object representing the UDP socket.

## Process
1. Receive the `transport` object via `connection_made`.
2. Assign `transport` to `self.node._transport`.
3. Log an info message indicating the UDP socket is ready on the configured listen port.

## Output
- `self.node._transport` is set.
- Info log message.
