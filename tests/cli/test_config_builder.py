import unittest
import os
import json
import tempfile
from p2pvpn.cli.config_builder import ConfigBuilder, ConfigValidationError
from p2pvpn.core.models.vpn_config import VPNConfig, PeerInfo, StunServerInfo

class TestConfigBuilder(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.test_dir.name, "config.json")
        
        self.default_json_content = {
            "local_ip": "10.0.0.1",
            "listen_port": 5555,
            "tap_name": "tap0",
            "prefix": 24,
            "mtu": 1500,
            "peers": [
                {"host": "10.0.0.2", "port": 5555}
            ],
            "stun_servers": [
                {"host": "stun.l.google.com", "port": 19302}
            ]
        }
        with open(self.config_path, 'w') as f:
            json.dump(self.default_json_content, f)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_build_from_json_only(self):
        """Test building config with only JSON provided."""
        cli_overrides = {}
        config = ConfigBuilder.build(cli_overrides, self.config_path)
        
        self.assertIsInstance(config, VPNConfig)
        self.assertEqual(config.local_ip, "10.0.0.1")
        self.assertEqual(config.listen_port, 5555)
        self.assertEqual(config.tap_name, "tap0")
        self.assertEqual(config.prefix, 24)
        self.assertEqual(len(config.peers), 1)
        self.assertEqual(config.peers[0].host, "10.0.0.2")
        self.assertEqual(len(config.stun_servers), 1)
        self.assertEqual(config.stun_servers[0].host, "stun.l.google.com")

    def test_build_with_cli_overrides(self):
        """Test that CLI overrides JSON."""
        cli_overrides = {
            "ip": "192.168.1.1",
            "port": 8080,
            "prefix": 16
        }
        config = ConfigBuilder.build(cli_overrides, self.config_path)
        
        self.assertEqual(config.local_ip, "192.168.1.1")
        self.assertEqual(config.listen_port, 8080)
        self.assertEqual(config.prefix, 16)
        # Check that non-overridden values from JSON are still present
        self.assertEqual(config.tap_name, "tap0")
        self.assertEqual(config.mtu, 1500)

    def test_build_with_complex_overrides(self):
        """Test overriding peers and stun_servers via CLI."""
        cli_overrides = {
            "peer": ["10.0.0.3:5555", "10.0.0.4:5556"],
            "stun_server": ["stun.server.com:19302"]
        }
        config = ConfigBuilder.build(cli_overrides, self.config_path)
        
        self.assertEqual(len(config.peers), 2)
        self.assertEqual(config.peers[0].host, "10.0.0.3")
        self.assertEqual(config.peers[0].port, 5555)
        self.assertEqual(config.peers[1].host, "10.0.0.4")
        self.assertEqual(config.peers[1].port, 5556)
        
        self.assertEqual(len(config.stun_servers), 1)
        self.assertEqual(config.stun_servers[0].host, "stun.server.com")

    def test_invalid_ip_validation(self):
        """Test that invalid IP raises ConfigValidationError."""
        cli_overrides = {"ip": "not-an-ip"}
        with self.assertRaises(ConfigValidationError) as cm:
            ConfigBuilder.build(cli_overrides, self.config_path)
        self.assertIn("Invalid local_ip", str(cm.exception))

    def test_invalid_port_validation(self):
        """Test that invalid port raises ConfigValidationError."""
        cli_overrides = {"port": 70000}
        with self.assertRaises(ConfigValidationError) as cm:
            ConfigBuilder.build(cli_overrides, self.config_path)
        self.assertIn("Invalid listen_port", str(cm.exception))

    def test_invalid_prefix_validation(self):
        """Test that invalid prefix raises ConfigValidationError."""
        cli_overrides = {"prefix": 33}
        with self.assertRaises(ConfigValidationError) as cm:
            ConfigBuilder.build(cli_overrides, self.config_path)
        self.assertIn("Invalid prefix", str(cm.exception))

    def test_invalid_mtu_validation(self):
        """Test that invalid MTU raises ConfigValidationError."""
        cli_overrides = {"mtu": 100}
        with self.assertRaises(ConfigValidationError) as cm:
            ConfigBuilder.build(cli_overrides, self.config_path)
        self.assertIn("Invalid MTU", str(cm.exception))

    def test_invalid_peer_format(self):
        """Test that invalid peer format raises ConfigValidationError."""
        cli_overrides = {"peer": ["invalid_peer"]}
        with self.assertRaises(ConfigValidationError) as cm:
            ConfigBuilder.build(cli_overrides, self.config_path)
        self.assertIn("Invalid peer format", str(cm.exception))

    def test_missing_json_file(self):
        """Test that missing JSON file raises ConfigValidationError."""
        with self.assertRaises(ConfigValidationError) as cm:
            ConfigBuilder.build({}, "non_existent_file.json")
        self.assertIn("Failed to load JSON config", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
