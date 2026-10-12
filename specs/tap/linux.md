# Linux TAP Backend (`_TAPLinux`)
Implements the TAP interface using `/dev/net/tun` and standard Linux networking tools.

## Core Responsibilities
- **Interface Creation**: Opens `/dev/net/tun` and uses `ioctl` (TUNSETIFF) to create/attach to a TAP device.
- **Network Configuration**:
    - Sets MTU via `ip link`.
    - Brings interface UP via `ip link`.
    - Configures IP address and subnet mask via `ip addr`.
- **Performance Tuning**: Disables hardware offloads (TSO, GSO, GRO, LRO, etc.) via `ethtool` to ensure packet integrity through the VPN.
- **TCP Optimization**: Implements MSS clamping using `iptables` (mangle table) for both incoming and outgoing TCP traffic to prevent fragmentation issues.
- **I/O Management**:
    - **Write**: Uses non-blocking `os.write` to send Ethernet frames.
    - **Read**: Uses `asyncio`'s `add_reader` to monitor the file descriptor via `epoll` and dispatch frames via a callback.
- **Cleanup**: Removes `iptables` rules, brings the interface down, flushes IP settings, and closes the file descriptor.
