# Logic: Configuration Building
## Description
Parses CLI arguments or reads a JSON configuration file to construct a unified configuration dictionary for the VPN node.

## Requirements
- Support loading from a JSON file via `--config`.
- Fallback to individual CLI arguments if no config file is provided.
- Parse peer addresses from `HOST:PORT` format.
- Include settings for local IP, listen port, TAP interface, network prefix, and STUN settings.

## Input
- `argparse.Namespace` object from CLI arguments or a JSON file path.

## Output
- A dictionary containing all necessary configuration keys.
