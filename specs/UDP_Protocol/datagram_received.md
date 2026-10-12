# Logic: Datagram Reception

## Description
When a UDP datagram is received, the protocol delegates the processing to the node.

## Input
- `data`: The raw bytes received from the network.
- `addr`: The address (IP and port) of the sender.

## Process
1. Receive `data` and `addr` via `datagram_received`.
2. Call `self.node._on_udp(data, addr)` to handle the data.

## Output
- Data processing is triggered in the node via `_on_udp`.
