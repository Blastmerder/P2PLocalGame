# Peer State Specification

## Initialization
A `Peer` object must be initialized with the following attributes:
- `host` (str): The IP address or hostname of the peer.
- `port` (int): The port number of the peer.
- `last_seen` (float, default 0.0): The timestamp of the last received packet.
- `mac` (bytes, optional): The MAC address of the peer.

## Properties
- `addr`: Returns a tuple of `(host, port)`.

## String Representation
- Method `__str__` should return a string in the format: `{host}:{port} [{status}] mac={mac_str}`.
- If `mac` is provided, `mac_str` is the MAC address in hexadecimal format separated by colons (e.g., `aa:bb:cc:dd:ee:ff`).
- If `mac` is `None`, `mac_str` is `"unknown"`.
