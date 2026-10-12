# Peer Confirmation and Liveness Specification

## Confirmation Logic
- A peer is considered **confirmed** if `last_seen > 0.0`.
- A peer is **not confirmed** if `last_seen == 0.0`.

## Liveness Logic (`is_alive`)
A peer is considered **alive** if and only if:
1. The peer is **confirmed**.
2. The time elapsed since `last_seen` is less than `PEER_TIMEOUT` seconds.

If either condition is not met, the peer is not alive.

## Status Property
The `status` property returns one of the following strings:
- `"pending"`: If the peer is not confirmed.
- `"alive"`: If the peer is confirmed and `is_alive()` is `True`.
- `"dead"`: If the peer is confirmed but `is_alive()` is `False`.
