# Logic: Main Async Loop & Lifecycle
## Description
Manages the asynchronous execution of the VPN node, including STUN discovery, TAP device setup, signal handling for graceful shutdown, and the core node runtime.

## Requirements
- Execute STUN discovery first.
- Display public address information to the user.
- Initialize the TAP device with configured parameters.
- Initialize and run the `VPNNode`.
- Handle OS signals (SIGINT, SIGTERM) to trigger a graceful shutdown of all running tasks.
- Handle Windows-specific keyboard interrupts (Ctrl+C).

## Input
- Configuration dictionary.

## Output
- Once finished, the node stops and logs the termination.
