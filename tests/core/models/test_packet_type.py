import unittest
from p2pvpn.core.models.packet_type import PacketType

class TestPacketType(unittest.TestCase):
    def test_packet_types_exist(self):
        self.assertEqual(PacketType.HELLO.name, "HELLO")
        self.assertEqual(PacketType.DATA.name, "DATA")

if __name__ == '__main__':
    unittest.main()
