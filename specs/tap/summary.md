# TAP Module Summary

`tap.py` provides a cross-platform TAP interface for a P2P L2 VPN, supporting Linux and Windows.

## Business Logics

1.  **TAP Interface Abstraction (`_TAPBase`)**: Defines a unified API for lifecycle management (setup/teardown) and data I/O (read/write) across different operating systems.
2.  **Linux Backend (`_TAPLinux`)**: Manages `/dev/net/tun` devices. It handles interface creation, IP/MTU configuration via `ip` commands, TCP MSS clamping via `iptables`, and disables hardware offloads via `ethtool`. It uses `asyncio`'s `epoll`-based reader.
3.  **Windows Backend (`_TAPWindows`)**: Interfaces with TAP-Windows6 drivers. It discovers adapters via the Registry, manages connectivity via `DeviceIoControl`, and configures networking via `netsh` and PowerShell. It implements I/O using a dedicated background thread for blocking overlapped reads.
4.  **Platform Factory (`TAPDevice`)**: Automatically selects the appropriate backend based on the current operating system.
5.  **Privilege Verification (`is_admin`)**: Checks for administrative/root permissions required for network configuration.
