import socket


def _make_udp_socket(port: int) -> socket.socket:
    """
    Создать UDP-сокет, готовый к биндингу на 0.0.0.0:port.

    SO_REUSEADDR обязательно — на Windows без него bind() падает
    с WSAEADDRINUSE если STUN-сокет ещё не до конца закрыт.
    SO_REUSEPORT — где доступно (Linux/BSD), позволяет нескольким
    сокетам слушать тот же порт одновременно.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
    sock.setblocking(False)
    sock.bind(("0.0.0.0", port))
    return sock

