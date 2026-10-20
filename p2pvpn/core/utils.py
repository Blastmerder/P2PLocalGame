import sys
import os

def is_admin() -> bool:
    """Check for administrative privileges: root on Linux, Administrator on Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.geteuid() == 0
