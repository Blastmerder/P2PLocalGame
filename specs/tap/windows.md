# Windows TAP Backend (`_TAPWindows`)
Implements the TAP interface using the TAP-Windows6 driver and Windows-specific APIs.

## Core Responsibilities
- **Adapter Discovery**: Scans the Windows Registry to find suitable TAP-Windows6 adapters, optionally filtering by a preferred name.
- **Device Access**: Opens the TAP device using `CreateFile` with an overlapped handle for asynchronous I/O.
- **Connectivity Management**: Controls the media status (connecting/disconnecting) via `DeviceIoControl` to simulate cable insertion/removal.
- **Network Configuration**:
    - Configures IP address and subnet mask using `netsh`.
    - Sets MTU using `netsh`.
    - Disables hardware offloads (LSO, Checksum Offload) via PowerShell commands.
- **I/O Management**:
    - **Write**: Uses `win32file.WriteFile` with overlapped structure for sending Ethernet frames.
    - **Read**: Spawns a dedicated background thread (`_read_loop`) to perform blocking overlapped reads, then dispatches frames to the `asyncio` event loop using `call_soon_threadsafe`.
- **Cleanup**: Stops the reader thread, resets media status, closes the device handle, and terminates the background thread.
