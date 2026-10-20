import unittest
from p2pvpn.core.models.vpn_config import VPNConfig

class TestVPNConfig(unittest.TestCase):
    def test_config_default_values(self):
        config = VPNConfig(
            local_ip="10.0.0.1",
            listen_port=5555,
            tap_name="tap0",
            prefix=24
        )
        self.assertEqual(config.mtu, 1500)
        self.assertEqual(config.keepalive_interval, 30)
        self.assertEqual(config.connection_timeout, 10)

    def test_config_from_dict(self):
        config_dict = {
            "local_ip": "10.0.0.1",
            "listen_port": 5555,
            "tap_name": "tap0",
            "prefix": 24,
            "mtu": 1400,
            "keepalive_interval": 60,
            "connection_timeout": 5
        }
        config = VPNConfig.from_dict(config_dict)
        self.assertEqual(config.mtu, 1400)
        self.assertEqual(config.keepalive_interval, 60)
        self.assertEqual(config.connection_timeout, 5)

if __name__ == '__main__':
    unittest.main()
