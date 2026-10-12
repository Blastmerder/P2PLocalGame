# VPN Detection Logic

## Purpose
Detects the presence of a VPN using multiple heuristics and indicators.

## Components
- `VPNDetector` (Interface): Defines the contract for VPN detection.
- `AdvancedVPNDetector` (Implementation):
    - `detect_vpn()`: Orchestrates multiple checks and calculates overall confidence.
    - `_check_rtt_difference()`: Compares UDP (STUN) vs TCP RTT; significant differences suggest VPN.
    - `_check_ttl()`: Checks IP Time-to-Live values for common VPN patterns.
    - `_check_dns_servers()`: Identifies if public or suspicious DNS servers are in use.
    - `_detect_vpn_interfaces()`: Looks for virtual interfaces (e.g., `tun`, `tap`, `wireguard`).
    - `_check_routing_table()`: Scans routing tables for VPN-specific subnets or gateway indicators.
    - `_check_ip_difference()`: Analyzes the relationship between local and external IP subnets.
    - `_calculate_total_confidence()`: Applies weighted logic to all detected indicators to produce a final status.

## Indicators Analyzed
- RTT Difference (Weight: 0.6)
- TTL Value (Weight: 0.4)
- DNS Privacy (Weight: 0.7)
- VPN Interfaces (Weight: 1.0)
- Routing Table (Weight: 0.9)
- IP Difference (Weight: 0.5)

## Dependencies
- `os`
- `socket`
- `time`
- `subprocess`
- `statistics`
