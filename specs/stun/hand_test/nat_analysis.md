# NAT Analysis Logic

## Purpose
Determines the type of NAT (Network Address Translation) present on the host.

## Components
- `NATAnalyzer` (Interface): Defines the contract for NAT analysis.
- `SimplSTUNClient`:
    - `get_nat_type()`: Determines NAT type (Open, Moderate, Strict, Symmetric) by checking port accessibility.
    - `get_external_address()`: Retrieves the public IP and a randomly allocated port via STUN.
    - `_check_port_accessibility()`: Tests various ports (53, 123, 443, etc.) to see if they are reachable/bindable via UDP.
- `NATAnalyzerImpl`:
    - `analyze()`: Orchestrates the analysis by combining external address, NAT type, and local IP data into a `NATResult`.

## Dependencies
- `socket`
- `time`
- `typing`
