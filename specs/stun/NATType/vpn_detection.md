# VPN Detection Logic
## Description
The `AdvancedVPNDetector` class implements the `VPNDetector` interface, using multiple heuristic methods to identify if a VPN is in use.

## Business Logic
1. **RTT (Round Trip Time) Analysis**:
   - Compares UDP RTT (measured via STUN) against TCP RTT (measured via connection to a public service).
   - A difference greater than 20ms is flagged as a potential VPN indicator.

2. **TTL (Time To Live) Analysis**:
   - Checks the TTL value of IP packets.
   - Detects potential intermediate nodes if the TTL value is significantly lower than standard platform defaults (e.g., < 64).

3. **DNS Privacy Analysis**:
   - Retrieves the system's DNS server list.
   - Flags the use of known public DNS servers (Google, Cloudflare, etc.) as a privacy indicator if they differ from typical ISP-provided DNS.

4. **Network Interface Analysis**:
   - Enumerates active network interfaces using system commands (`ip link` or `ipconfig`).
   - Searches for common VPN-related keywords in interface names (e.g., `tun`, `tap`, `wireguard`, `vpn`).

5. **Routing Table Analysis**:
   - Inspects the system routing table for suspicious routes or interfaces (e.g., `0.0.0.0` via a VPN interface or typical VPN subnets like `10.8.0.0`).

6. **IP Address Difference Analysis**:
   - Compares the internal (private) IP with the external (public) IP.
   - Checks if the internal IP is in a private range (RFC 1918) and if the external IP falls within the same subnet, which is suspicious.

7. **Confidence Calculation**:
   - Aggregates all indicators using a weighted system where some methods (like interface detection) have higher weight than others (like TTL).
   - Determines the overall `VPNStatus` (DETECTED, POSSIBLE, NOT_DETECTED) based on the final confidence score.
