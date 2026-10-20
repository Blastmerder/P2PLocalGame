import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import argparse
import asyncio
import sys
import os
import platform

from p2pvpn.cli.main import main_async, check_privileges
from p2pvpn.core.models.vpn_config import VPNConfig, PeerInfo, StunServerInfo
from p2pvpn.transport.udp.stun import STUNResult

class TestCLI(unittest.TestCase):

    def setUp(self):
        # Create a dummy config
        self.mock_config = VPNConfig(
            local_ip="10.0.0.1",
            listen_port=5555,
            tap_name="tap0",
            prefix=24,
            peers=[],
            skip_stun=False,
            stun_timeout=3.0,
            stun_servers=[],
            mtu=1500
        )

    @patch('p2pvpn.cli.main.is_admin')
    def test_check_privileges_success(self, mock_is_admin):
        mock_is_admin.return_value = True
        try:
            check_privileges()
        except SystemExit:
            self.fail("check_privileges() raised SystemExit unexpectedly!")

    @patch('p2pvpn.cli.main.is_admin')
    @patch('sys.exit')
    def test_check_privileges_failure(self, mock_exit, mock_is_admin):
        mock_is_admin.return_value = False
        check_privileges()
        mock_exit.assert_called_once()

    @patch('p2pvpn.cli.main.ConfigBuilder.build')
    @patch('p2pvpn.cli.main.discover_async')
    @patch('p2pvpn.cli.main.UDPTransport')
    @patch('p2pvpn.cli.main.TAPInterface')
    @patch('p2pvpn.cli.main.PeerManager')
    @patch('p2pvpn.cli.main.Engine')
    @patch('p2pvpn.cli.main.check_privileges')
    @patch('p2pvpn.cli.main.is_admin')
    def test_main_async_success(self, mock_is_admin, mock_check_privs, mock_engine_cls, 
                               mock_peer_manager_cls, mock_tap_cls, mock_udp_cls, 
                               mock_discover_async, mock_config_build):
        # Setup mocks
        mock_is_admin.return_value = True
        mock_check_privs.return_value = None
        mock_config_build.return_value = self.mock_config
        
        mock_stun_result = STUNResult(public_ip="1.2.3.4", public_port=12345, server_used="stun.l.google.com")
        mock_discover_async.return_value = mock_stun_result

        mock_udp_inst = mock_udp_cls.return_value
        mock_udp_inst.open = AsyncMock()
        mock_udp_inst.close = AsyncMock()

        mock_tap_inst = mock_tap_cls.return_value
        mock_tap_inst.setup = AsyncMock()
        mock_tap_inst.teardown = AsyncMock()

        mock_peer_manager_inst = mock_peer_manager_cls.return_value
        
        mock_engine_inst = mock_engine_cls.return_value
        mock_engine_inst.run = AsyncMock()
        mock_engine_inst.stop = AsyncMock()

        # Mocking sys.argv to simulate command line arguments
        test_args = [
            'p2pvpn/cli/main.py',
            '--ip', '10.0.0.2',
            '--port', '6666',
            '--tap', 'tap1',
            '--peer', '1.1.1.1:1111',
            '--peer', '2.2.2.2:2222',
            '--no-stun'
        ]
        
        with patch.object(sys, 'argv', test_args):
            args = argparse.Namespace(
                config=None,
                ip='10.0.0.2',
                port=6666,
                tap='tap1',
                prefix=24,
                peer=['1.1.1.1:1111', '2.2.2.2:2222'],
                no_stun=True,
                stun_server=None,
                stun_timeout=3.0,
                debug=False
            )
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(main_async(args))
            finally:
                loop.close()

        # Verifications
        # Check if cli_overrides were correctly parsed from sys.argv
        mock_config_build.assert_called_once_with({
            'ip': '10.0.0.2',
            'port': 6666,
            'tap': 'tap1',
            'peer': ['1.1.1.1:1111', '2.2.2.2:2222'],
            'no_stun': True
        }, None)

        # Verify Engine was instantiated with correct config
        args_to_engine, kwargs_to_engine = mock_engine_cls.call_args
        self.assertEqual(args_to_engine[3], self.mock_config) # config is 4th arg (index 3)
        
        # Verify components were started
        mock_udp_inst.open.assert_called_once()
        mock_tap_inst.setup.assert_called_once()
        mock_engine_inst.run.assert_called_once()

    @patch('p2pvpn.cli.main.ConfigBuilder.build')
    @patch('p2pvpn.cli.main.discover_async')
    @patch('p2pvpn.cli.main.UDPTransport')
    @patch('p2pvpn.cli.main.TAPInterface')
    @patch('p2pvpn.cli.main.PeerManager')
    @patch('p2pvpn.cli.main.Engine')
    @patch('p2pvpn.cli.main.check_privileges')
    @patch('p2pvpn.cli.main.is_admin')
    def test_main_async_stun_skipped(self, mock_is_admin, mock_check_privs, mock_engine_cls, 
                                   mock_peer_manager_cls, mock_tap_cls, mock_udp_cls, 
                                   mock_discover_async, mock_config_build):
        # Setup mocks
        mock_is_admin.return_value = True
        mock_check_privs.return_value = None
        
        # Config without STUN
        from dataclasses import replace
        config_no_stun = replace(self.mock_config, skip_stun=True)
        mock_config_build.return_value = config_no_stun

        mock_udp_inst = mock_udp_cls.return_value
        mock_udp_inst.open = AsyncMock()
        mock_udp_inst.close = AsyncMock()

        mock_tap_inst = mock_tap_cls.return_value
        mock_tap_inst.setup = AsyncMock()
        mock_tap_inst.teardown = AsyncMock()

        mock_peer_manager_inst = mock_peer_manager_cls.return_value
        
        mock_engine_inst = mock_engine_cls.return_value
        mock_engine_inst.run = AsyncMock()
        mock_engine_inst.stop = AsyncMock()

        with patch.object(sys, 'argv', ['p2pvpn/cli/main.py', '--no-stun']):
            args = argparse.Namespace(
                config=None,
                ip='10.0.0.1',
                port=5555,
                tap='tap0',
                prefix=24,
                peer=None,
                no_stun=True,
                stun_server=None,
                stun_timeout=3.0,
                debug=False
            )
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(main_async(args))
            finally:
                loop.close()

        # Verify engine ran and STUN was not called
        mock_engine_inst.run.assert_called_once()
        mock_discover_async.assert_not_called()

if __name__ == '__main__':
    unittest.main()
