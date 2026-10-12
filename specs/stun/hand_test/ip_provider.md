# IP Provider Logic

## Purpose
Retrieves the local (internal) and public (external) IP addresses of the machine.

## Components
- `IPProvider` (Interface): Defines the contract for IP retrieval.
- `LocalIPProvider` (Implementation):
    - `get_internal_ip()`: Uses a UDP socket connection to a known public IP (`8.8.8.8:80`) to identify the local interface IP.
    - `get_external_ip()`: Queries a list of STUN servers (`stun.l.google.com`, etc.) using a STUN Binding Request to discover the public mapping.
    - `_query_stun()`: Handles the low-level socket communication and STUN protocol request.
    - `_parse_stun_response()`: Parses the binary STUN response to extract the `MAPPED-ADDRESS` attribute.

## Dependencies
- `socket`
- `struct`
- `typing`
