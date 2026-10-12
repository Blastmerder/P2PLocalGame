# Logic: STUN Discovery
## Description
Determines the public IP address and port of the node using the STUN protocol to facilitate NAT hole punching.

## Requirements
- Bind the STUN socket to the same port as the VPN listen port to ensure NAT mapping consistency.
- Allow skipping STUN discovery via configuration.
- Support providing custom STUN servers.
- Handle STUN discovery failures gracefully by continuing execution.
- Return the public IP and port if successful.

## Input
- Configuration dictionary containing `listen_port`, `skip_stun`, and `stun_servers`.

## Output
- An optional `STUNResult` object containing the public IP and port.
