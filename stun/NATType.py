from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import socket
import struct
import time
import subprocess
import os
import re
from enum import Enum
from statistics import mean, stdev


# ============================================================================
# Перечисления
# ============================================================================

class NATType(Enum):
    """Типы NAT"""
    UNKNOWN = "Unknown"
    OPEN = "Open (Full Cone)"
    MODERATE = "Moderate (Address Restricted Cone)"
    STRICT = "Strict (Port Restricted Cone)"
    SYMMETRIC = "Symmetric"


class VPNStatus(Enum):
    """Статус VPN"""
    NOT_DETECTED = "VPN not detected"
    POSSIBLE = "Possible VPN usage"
    DETECTED = "VPN detected"


class VPNConfidence(Enum):
    """Уровень уверенности в обнаружении VPN"""
    LOW = (0.3, "Low (< 30%)")
    MEDIUM = (0.6, "Medium (30%-60%)")
    HIGH = (0.8, "High (60%-80%)")
    VERY_HIGH = (1.0, "Very High (> 80%)")


# ============================================================================
# Модели данных
# ============================================================================

@dataclass
class NATResult:
    """Результат определения NAT"""
    nat_type: NATType
    external_ip: str
    internal_ip: str
    port: int
    timestamp: float


@dataclass
class VPNIndicator:
    """Отдельный индикатор VPN"""
    name: str
    detected: bool
    confidence: float  # 0.0 - 1.0
    explanation: str


@dataclass
class VPNResult:
    """Результат проверки VPN"""
    vpn_status: VPNStatus
    confidence: float  # Общая уверенность
    indicators: List[VPNIndicator] = field(default_factory=list)
    rtt_difference: Optional[float] = None
    ttl_value: Optional[int] = None
    dns_servers: List[str] = field(default_factory=list)
    gateway_ip: Optional[str] = None
    active_interfaces: List[str] = field(default_factory=list)


@dataclass
class DiagnosticReport:
    """Полный отчёт о диагностике"""
    nat_result: NATResult
    vpn_result: VPNResult


# ============================================================================
# Абстрактные интерфейсы
# ============================================================================

class IPProvider(ABC):
    """Интерфейс для получения IP адреса"""
    
    @abstractmethod
    def get_external_ip(self) -> str:
        pass
    
    @abstractmethod
    def get_internal_ip(self) -> str:
        pass


class VPNDetector(ABC):
    """Интерфейс для определения VPN"""
    
    @abstractmethod
    def detect_vpn(self) -> VPNResult:
        pass


class NATAnalyzer(ABC):
    """Интерфейс для анализа NAT"""
    
    @abstractmethod
    def analyze(self) -> NATResult:
        pass


# ============================================================================
# IP Provider (получение IP адресов через STUN)
# ============================================================================

class LocalIPProvider(IPProvider):
    """Получение локального и внешнего IP адреса"""
    
    def __init__(self):
        self._external_ip_cache: Optional[str] = None
        self._internal_ip_cache: Optional[str] = None
    
    def get_internal_ip(self) -> str:
        """Получить локальный IP"""
        if self._internal_ip_cache:
            return self._internal_ip_cache
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            self._internal_ip_cache = ip
            return ip
        except Exception:
            return "127.0.0.1"
    
    def get_external_ip(self) -> str:
        """Получить публичный IP через STUN сервер"""
        if self._external_ip_cache:
            return self._external_ip_cache
        
        stun_servers = [
            ("stun.l.google.com", 19302),
            ("stun1.l.google.com", 19302),
            ("stun2.l.google.com", 19302),
            ("stun3.l.google.com", 19302),
        ]
        
        for server_ip, server_port in stun_servers:
            try:
                external_ip = self._query_stun(server_ip, server_port)
                if external_ip:
                    self._external_ip_cache = external_ip
                    return external_ip
            except Exception:
                continue
        
        return "Unknown"
    
    @staticmethod
    def _query_stun(server_ip: str, server_port: int) -> Optional[str]:
        """Запросить STUN сервер"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        
        # STUN Binding Request
        stun_request = struct.pack('!HHI4s', 0x0001, 0, 0x2112A442, b'\x00\x00\x00\x00')
        sock.sendto(stun_request, (server_ip, server_port))
        
        response, _ = sock.recvfrom(512)
        sock.close()
        
        return LocalIPProvider._parse_stun_response(response)
    
    @staticmethod
    def _parse_stun_response(response: bytes) -> Optional[str]:
        """Разобрать STUN ответ"""
        try:
            if len(response) < 20:
                return None
            
            offset = 20
            while offset < len(response):
                if offset + 4 > len(response):
                    break
                
                attr_type = struct.unpack('!H', response[offset:offset+2])[0]
                attr_length = struct.unpack('!H', response[offset+2:offset+4])[0]
                
                if attr_type == 0x0020 and attr_length >= 8:  # MAPPED-ADDRESS
                    family = response[offset+5]
                    if family == 1:  # IPv4
                        ip_bytes = response[offset+8:offset+12]
                        ip = ".".join(str(b) for b in ip_bytes)
                        return ip
                
                offset += 4 + attr_length
        except Exception:
            pass
        
        return None


# ============================================================================
# Продвинутый VPN Детектор
# ============================================================================

class AdvancedVPNDetector(VPNDetector):
    """Продвинутый детектор VPN с множественными методами"""
    
    def __init__(self, ip_provider: IPProvider):
        self.ip_provider = ip_provider
        self.indicators: List[VPNIndicator] = []
    
    def detect_vpn(self) -> VPNResult:
        """Запустить все проверки VPN"""
        
        print("  🔍 Проверяем RTT разницу...")
        rtt_diff = self._check_rtt_difference()
        
        print("  🔍 Проверяем TTL...")
        ttl = self._check_ttl()
        
        print("  🔍 Проверяем DNS серверы...")
        dns_servers = self._check_dns_servers()
        dns_indicator = self._check_dns_privacy(dns_servers)
        
        print("  🔍 Проверяем сетевые интерфейсы...")
        interfaces = self._check_network_interfaces()
        interface_indicator = self._detect_vpn_interfaces(interfaces)
        
        print("  🔍 Проверяем маршруты...")
        route_indicator = self._check_routing_table()
        
        print("  🔍 Проверяем IP различие...")
        ip_indicator = self._check_ip_difference()
        
        # Добавляем все индикаторы
        self.indicators.extend([
            dns_indicator,
            interface_indicator,
            route_indicator,
            ip_indicator
        ])
        
        # Если RTT разница значительна, добавляем индикатор
        if rtt_diff is not None and rtt_diff > 20:  # > 20ms разница
            self.indicators.append(VPNIndicator(
                name="RTT Difference",
                detected=True,
                confidence=min(rtt_diff / 100, 1.0),
                explanation=f"RTT разница составляет {rtt_diff:.1f}ms (ожидается > 20ms для VPN)"
            ))
        
        # Если TTL отличается от стандартного
        if ttl is not None and ttl < 64:
            self.indicators.append(VPNIndicator(
                name="TTL Value",
                detected=True,
                confidence=0.3,
                explanation=f"TTL значение {ttl} (стандартное 64), может указывать на промежуточные узлы"
            ))
        
        # Вычисляем общую уверенность
        total_confidence = self._calculate_total_confidence()
        
        # Определяем статус VPN
        vpn_status = self._determine_vpn_status(total_confidence)
        
        return VPNResult(
            vpn_status=vpn_status,
            confidence=total_confidence,
            indicators=self.indicators,
            rtt_difference=rtt_diff,
            ttl_value=ttl,
            dns_servers=dns_servers,
            gateway_ip=self._get_gateway_ip(),
            active_interfaces=interfaces
        )
    
    # ========== RTT анализ ==========
    
    def _check_rtt_difference(self) -> Optional[float]:
        """
        Сравнить RTT через разные способы подключения.
        Если разница > 20ms, вероятен VPN
        """
        try:
            # Способ 1: UDP STUN пинг
            udp_rtt = self._measure_udp_rtt()
            
            # Способ 2: TCP пинг (если доступен)
            tcp_rtt = self._measure_tcp_rtt()
            
            if udp_rtt is not None and tcp_rtt is not None:
                difference = abs(tcp_rtt - udp_rtt)
                return difference
            
            return None
        except Exception as e:
            print(f"    ⚠️ Ошибка при измерении RTT: {e}")
            return None
    
    @staticmethod
    def _measure_udp_rtt() -> Optional[float]:
        """Измерить RTT через UDP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            
            times = []
            for _ in range(3):
                start = time.time()
                stun_request = struct.pack('!HHI4s', 0x0001, 0, 0x2112A442, b'\x00\x00\x00\x00')
                sock.sendto(stun_request, ("stun.l.google.com", 19302))
                sock.recvfrom(512)
                elapsed = (time.time() - start) * 1000  # в ms
                times.append(elapsed)
            
            sock.close()
            return mean(times) if times else None
        except Exception:
            return None
    
    @staticmethod
    def _measure_tcp_rtt() -> Optional[float]:
        """Измерить RTT через TCP"""
        try:
            times = []
            for _ in range(3):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                
                start = time.time()
                sock.connect(("8.8.8.8", 53))  # Google DNS
                elapsed = (time.time() - start) * 1000  # в ms
                times.append(elapsed)
                sock.close()
            
            return mean(times) if times else None
        except Exception:
            return None
    
    # ========== TTL анализ ==========
    
    def _check_ttl(self) -> Optional[int]:
        """Проверить TTL (Time To Live) в IP пакетах"""
        try:
            if os.name == 'nt':  # Windows
                return self._check_ttl_windows()
            else:  # Linux/Mac
                return self._check_ttl_unix()
        except Exception:
            return None
    
    @staticmethod
    def _check_ttl_windows() -> Optional[int]:
        """Получить TTL в Windows"""
        try:
            result = subprocess.run(
                ["ipconfig", "/all"],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Стандартный TTL для Windows обычно 128
            return 128
        except Exception:
            return None
    
    @staticmethod
    def _check_ttl_unix() -> Optional[int]:
        """Получить TTL в Unix/Linux"""
        try:
            # Стандартный TTL для Linux обычно 64
            return 64
        except Exception:
            return None
    
    # ========== DNS анализ ==========
    
    @staticmethod
    def _check_dns_servers() -> List[str]:
        """Получить список DNS серверов"""
        dns_servers = []
        
        try:
            # Linux/Mac
            if os.path.exists("/etc/resolv.conf"):
                with open("/etc/resolv.conf", "r") as f:
                    for line in f:
                        if line.startswith("nameserver"):
                            dns_servers.append(line.split()[1])
        except Exception:
            pass
        
        try:
            # Windows
            if os.name == 'nt':
                result = subprocess.run(
                    ["ipconfig", "/all"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split('\n'):
                    if "DNS Servers" in line or "DNS сервер" in line.lower():
                        # Парсим DNS адреса
                        parts = line.split(':')
                        if len(parts) > 1:
                            dns = parts[1].strip()
                            if dns:
                                dns_servers.append(dns)
        except Exception:
            pass
        
        # Fallback: использовать стандартные DNS
        if not dns_servers:
            dns_servers = ["8.8.8.8", "1.1.1.1"]
        
        return dns_servers
    
    def _check_dns_privacy(self, dns_servers: List[str]) -> VPNIndicator:
        """Проверить приватность DNS"""
        suspicious_dns = {
            "8.8.8.8": "Google DNS (public)",
            "8.8.4.4": "Google DNS (public)",
            "1.1.1.1": "Cloudflare DNS (public)",
            "9.9.9.9": "Quad9 DNS (public)",
            "127.0.0.1": "Loopback (suspicious)",
        }
        

        detected = False
        confidence = 0.0
        explanation = ""

        # Определяем ISP DNS (обычно приватные адреса)
        isp_dns_prefixes = ["192.168.", "10.", "172."]

        for dns in dns_servers:
            # Если используется публичный DNS вместо ISP - признак VPN
            if dns in suspicious_dns:
                explanation = f"Использующиеся DNS: {', '.join(dns_servers)} (публичные сервера)"
                detected = True
                confidence = 0.6
                break

            # Если используется локальный/ISP DNS - обычно нормально
            is_isp_dns = any(dns.startswith(prefix) for prefix in isp_dns_prefixes)
            if is_isp_dns:
                explanation = f"Используется ISP DNS: {dns} (нормально)"
                detected = False
                confidence = 0.1

        if not explanation:
            explanation = f"DNS серверы: {', '.join(dns_servers)}"

        return VPNIndicator(
            name="DNS Privacy",
            detected=detected,
            confidence=confidence,
            explanation=explanation
        )

    # ========== Сетевые интерфейсы ==========

    def _check_network_interfaces(self) -> List[str]:
        """Получить список активных сетевых интерфейсов"""
        interfaces = []

        try:
            if os.name == 'nt':  # Windows
                result = subprocess.run(
                    ["ipconfig"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                # Парсим имена адаптеров
                for line in result.stdout.split('\n'):
                    if "adapter" in line.lower() or "адаптер" in line.lower():
                        parts = line.split(':')
                        if parts:
                            name = parts[0].strip()
                            if name:
                                interfaces.append(name)
            else:  # Linux/Mac
                result = subprocess.run(
                    ["ip", "link", "show"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split('\n'):
                    if ':' in line and not line.startswith(' '):
                        parts = line.split(':')
                        name = parts[1].strip()
                        if name:
                            interfaces.append(name)
        except Exception:
            pass

        return interfaces

    def _detect_vpn_interfaces(self, interfaces: List[str]) -> VPNIndicator:
        """Обнаружить VPN интерфейсы"""

        vpn_keywords = [
            "vpn", "tun", "tap", "wintun", "openvpn",
            "wireguard", "docker", "veth", "vlan"
        ]

        vpn_interfaces = [
            iface for iface in interfaces
            if any(keyword in iface.lower() for keyword in vpn_keywords)
        ]

        detected = len(vpn_interfaces) > 0
        confidence = 0.9 if detected else 0.0

        explanation = (
            f"Обнаружены VPN интерфейсы: {', '.join(vpn_interfaces)}"
            if detected
            else f"VPN интерфейсы не обнаружены. Активные: {', '.join(interfaces[:3])}"
        )

        return VPNIndicator(
            name="VPN Interfaces",
            detected=detected,
            confidence=confidence,
            explanation=explanation
        )

    # ========== Таблица маршрутизации ==========

    def _check_routing_table(self) -> VPNIndicator:
        """Проверить таблицу маршрутизации на признаки VPN"""

        try:
            if os.name == 'nt':  # Windows
                result = subprocess.run(
                    ["route", "print"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
            else:  # Linux/Mac
                result = subprocess.run(
                    ["route", "-n"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

            output = result.stdout.lower()

            # Признаки VPN в маршрутах
            vpn_indicators = [
                "vpn", "tun", "tap", "wintun", "0.0.0.0",
                "10.0.0.0", "10.8.0.0"  # стандартные VPN подсети
            ]

            detected = any(indicator in output for indicator in vpn_indicators)
            confidence = 0.7 if detected else 0.0

            explanation = (
                "VPN маршруты обнаружены в таблице маршрутизации"
                if detected
                else "Стандартные маршруты (VPN не обнаружен)"
            )

            return VPNIndicator(
                name="Routing Table",
                detected=detected,
                confidence=confidence,
                explanation=explanation
            )

        except Exception as e:
            return VPNIndicator(
                name="Routing Table",
                detected=False,
                confidence=0.0,
                explanation=f"Не удалось проверить таблицу маршрутизации: {e}"
            )

    # ========== IP анализ ==========

    def _check_ip_difference(self) -> VPNIndicator:
        """Анализировать различие между локальным и внешним IP"""

        internal_ip = self.ip_provider.get_internal_ip()
        external_ip = self.ip_provider.get_external_ip()

        try:
            # Парсим IP адреса
            internal_parts = list(map(int, internal_ip.split(".")))
            external_parts = list(map(int, external_ip.split(".")))

            # Обычно они из разных подсетей
            same_subnet = internal_parts[:2] == external_parts[:2]

            # Если локальный в приватной сети а внешний в публичной - нормально
            internal_is_private = self._is_private_ip(internal_ip)
            external_is_public = not self._is_private_ip(external_ip)

            detected = same_subnet and internal_is_private  # Подозрительно если в одной подсети
            confidence = 0.5 if detected else 0.1

            explanation = (
                f"Внутренний: {internal_ip}, Внешний: {external_ip} "
                f"(находятся в {'одной' if same_subnet else 'разных'} подсети)"
            )

            return VPNIndicator(
                name="IP Difference",
                detected=detected,
                confidence=confidence,
                explanation=explanation
            )

        except Exception as e:
            return VPNIndicator(
                name="IP Difference",
                detected=False,
                confidence=0.0,
                explanation=f"Ошибка анализа IP: {e}"
            )

    @staticmethod
    def _is_private_ip(ip: str) -> bool:
        """Проверить является ли IP приватным"""
        try:
            parts = list(map(int, ip.split(".")))
            # RFC 1918 приватные IP
            if parts[0] == 10:
                return True
            if parts[0] == 172 and 16 <= parts[1] <= 31:
                return True
            if parts[0] == 192 and parts[1] == 168:
                return True
            return False
        except Exception:
            return False

    @staticmethod
    def _get_gateway_ip() -> Optional[str]:
        """Получить IP шлюза"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            gateway = sock.getsockname()[0]
            sock.close()
            return gateway
        except Exception:
            return None

    def _calculate_total_confidence(self) -> float:
        """Вычислить общую уверенность в наличии VPN"""
        if not self.indicators:
            return 0.0

        # Взвешиваем индикаторы
        weights = {
            "VPN Interfaces": 1.0,      # Самый надёжный
            "Routing Table": 0.9,
            "DNS Privacy": 0.7,
            "IP Difference": 0.5,
            "TTL Value": 0.4,
            "RTT Difference": 0.6,
        }

        total_weight = 0.0
        weighted_sum = 0.0

        for indicator in self.indicators:
            weight = weights.get(indicator.name, 0.5)
            if indicator.detected:
                weighted_sum += indicator.confidence * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0

        return min(weighted_sum / total_weight, 1.0)

    def _determine_vpn_status(self, confidence: float) -> VPNStatus:
        """Определить статус VPN на основе уверенности"""
        if confidence >= 0.7:
            return VPNStatus.DETECTED
        elif confidence >= 0.4:
            return VPNStatus.POSSIBLE
        else:
            return VPNStatus.NOT_DETECTED


# ============================================================================
# NAT анализатор
# ============================================================================

class SimplSTUNClient:
    """Простой STUN клиент для определения NAT"""

    def __init__(self, ip_provider: IPProvider):
        self.ip_provider = ip_provider

    def get_nat_type(self) -> NATType:
        """Определить тип NAT"""
        open_ports = self._check_port_accessibility()

        if len(open_ports) >= 3:
            return NATType.OPEN
        elif len(open_ports) >= 1:
            return NATType.MODERATE
        else:
            return NATType.STRICT

    def get_external_address(self) -> Tuple[str, int]:
        """Получить внешний адрес и порт"""
        external_ip = self.ip_provider.get_external_ip()
        port = self._get_available_port()
        return (external_ip, port)

    @staticmethod
    def _check_port_accessibility() -> list:
        """Проверить доступность различных портов"""
        accessible_ports = []
        test_ports = [53, 123, 443, 80, 19302, 5353]

        for port in test_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(1)
                sock.bind(("0.0.0.0", port))
                sock.close()
                accessible_ports.append(port)
            except OSError:
                pass

        return accessible_ports

    @staticmethod
    def _get_available_port() -> int:
        """Получить доступный случайный порт"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port


class NATAnalyzerImpl(NATAnalyzer):
    """Реализация анализатора NAT"""

    def __init__(self, stun_client: SimplSTUNClient, ip_provider: IPProvider):
        self.stun_client = stun_client
        self.ip_provider = ip_provider

    def analyze(self) -> NATResult:
        """Анализировать NAT"""
        external_ip, port = self.stun_client.get_external_address()
        nat_type = self.stun_client.get_nat_type()
        internal_ip = self.ip_provider.get_internal_ip()

        return NATResult(
            nat_type=nat_type,
            external_ip=external_ip,
            internal_ip=internal_ip,
            port=port,
            timestamp=time.time()
        )


# ============================================================================
# Диагностический сервис
# ============================================================================

class DiagnosticService:
    """Главный диагностический сервис"""

    def __init__(self, nat_analyzer: NATAnalyzer, vpn_detector: VPNDetector):
        self.nat_analyzer = nat_analyzer
        self.vpn_detector = vpn_detector

    def run_diagnostics(self) -> DiagnosticReport:
        """Запустить полную диагностику"""
        print("\n" + "="*70)
        print("🔍 ДИАГНОСТИКА NAT И VPN")
        print("="*70 + "\n")

        print("📡 Анализ NAT...")
        nat_result = self.nat_analyzer.analyze()

        print("\n🔐 Анализ VPN...")
        vpn_result = self.vpn_detector.detect_vpn()

        return DiagnosticReport(
            nat_result=nat_result,
            vpn_result=vpn_result
        )


# ============================================================================
# Форматер отчётов
# ============================================================================

class ReportFormatter:
    """Форматирование отчётов"""

    @staticmethod
    def format_report(report: DiagnosticReport) -> str:
        """Форматировать полный отчёт"""
        nat = report.nat_result
        vpn = report.vpn_result

        # Форматируем индикаторы VPN
        indicators_text = ReportFormatter._format_vpn_indicators(vpn.indicators)

        # Статус VPN с цветовым кодом
        vpn_status_icon = ReportFormatter._get_vpn_status_icon(vpn.vpn_status)

        output = f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║                     ПОЛНЫЙ ДИАГНОСТИЧЕСКИЙ ОТЧЁТ                         ║
║                         NAT И VPN АНАЛИЗ                                  ║
╚═══════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📡 ИНФОРМАЦИЯ О NAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • Тип NAT:              {ReportFormatter._get_nat_icon(nat.nat_type)} {nat.nat_type.value}
  • Внешний IP:           {nat.external_ip}
  • Локальный IP:         {nat.internal_ip}
  • Порт:                 {nat.port}
  • Время проверки:       {time.ctime(nat.timestamp)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔐 ИНФОРМАЦИЯ О VPN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • Статус VPN:           {vpn_status_icon} {vpn.vpn_status.value}
    • Уверенность:          {ReportFormatter._format_confidence(vpn.confidence)}
  • IP шлюза:             {vpn.gateway_ip or 'Не определён'}
  • DNS серверы:          {', '.join(vpn.dns_servers[:2]) if vpn.dns_servers else 'Unknown'}
  • Активные интерфейсы:  {', '.join(vpn.active_interfaces[:3]) if vpn.active_interfaces else 'Unknown'}

  └─ RTT разница:         {f'{vpn.rtt_difference:.1f}ms' if vpn.rtt_difference else 'N/A'}
  └─ TTL значение:        {vpn.ttl_value if vpn.ttl_value else 'N/A'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔬 ДЕТАЛЬНЫЙ АНАЛИЗ ИНДИКАТОРОВ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{indicators_text}

╚═══════════════════════════════════════════════════════════════════════════╝
"""
        return output

    @staticmethod
    def _format_vpn_indicators(indicators: List[VPNIndicator]) -> str:
        """Форматировать индикаторы VPN"""
        lines = []

        for i, indicator in enumerate(indicators, 1):
            status_icon = "✓" if indicator.detected else "✗"
            confidence_bar = ReportFormatter._create_confidence_bar(indicator.confidence)

            lines.append(f"  {i}. [{status_icon}] {indicator.name}")
            lines.append(f"     Уверенность: {confidence_bar} {indicator.confidence*100:.0f}%")
            lines.append(f"     {indicator.explanation}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _create_confidence_bar(confidence: float) -> str:
        """Создать визуальную полоску уверенности"""
        bar_length = 20
        filled = int(bar_length * confidence)
        bar = "█" * filled + "░" * (bar_length - filled)
        return f"[{bar}]"

    @staticmethod
    def _format_confidence(confidence: float) -> str:
        """Форматировать значение уверенности"""
        bar = ReportFormatter._create_confidence_bar(confidence)
        percentage = confidence * 100

        if confidence >= 0.7:
            level = "Высокая"
        elif confidence >= 0.4:
            level = "Средняя"
        else:
            level = "Низкая"

        return f"{bar} {percentage:.0f}% ({level})"

    @staticmethod
    def _get_vpn_status_icon(status: VPNStatus) -> str:
        """Получить иконку статуса VPN"""
        icons = {
            VPNStatus.DETECTED: "🔒",
            VPNStatus.POSSIBLE: "⚠️",
            VPNStatus.NOT_DETECTED: "🔓",
        }
        return icons.get(status, "❓")

    @staticmethod
    def _get_nat_icon(nat_type: NATType) -> str:
        """Получить иконку типа NAT"""
        icons = {
            NATType.OPEN: "✓",
            NATType.MODERATE: "◐",
            NATType.STRICT: "✗",
            NATType.SYMMETRIC: "↔️",
            NATType.UNKNOWN: "?",
        }
        return icons.get(nat_type, "?")


# ============================================================================
# Рекомендации
# ============================================================================

class RecommendationEngine:
    """Генератор рекомендаций"""

    @staticmethod
    def get_recommendations(report: DiagnosticReport) -> str:
        """Получить рекомендации на основе отчёта"""
        recommendations = []

        nat = report.nat_result
        vpn = report.vpn_result

        # Рекомендации по NAT
        if nat.nat_type == NATType.SYMMETRIC:
            recommendations.append(
                "⚠️  СИММЕТРИЧНЫЙ NAT: Ваш NAT сложный для P2P приложений. "
                "Рекомендуется использовать VPN для улучшения совместимости."
            )
        elif nat.nat_type == NATType.STRICT:
            recommendations.append(
                "⚠️  СТРОГИЙ NAT: Возможны проблемы с некоторыми приложениями. "
                "Рассмотрите использование VPN или настройку маршрутизатора."
            )
        elif nat.nat_type == NATType.MODERATE:
            recommendations.append(
                "ℹ️  УМЕРЕННЫЙ NAT: Некоторые приложения могут требовать оптимизации. "
                "Для повышения производительности рекомендуется VPN."
            )
        else:
            recommendations.append(
                "✓ ОТКРЫТЫЙ NAT: Идеальная конфигурация для большинства приложений."
            )

        # Рекомендации по VPN
        if vpn.vpn_status == VPNStatus.NOT_DETECTED:
            recommendations.append(
                "ℹ️  VPN НЕ ОБНАРУЖЕН: Для повышения приватности и безопасности "
                "рекомендуется использовать надёжный VPN сервис."
            )
        elif vpn.vpn_status == VPNStatus.DETECTED:
            recommendations.append(
                "✓ VPN АКТИВЕН: Ваше соединение защищено. "
                "Убедитесь, что это надёжный и доверенный провайдер."
            )

            # Проверяем DNS утечку
            dns_leak_detected = any(
                ind.name == "DNS Privacy" and ind.detected
                for ind in vpn.indicators
            )
            if dns_leak_detected:
                recommendations.append(
                    "⚠️  DNS УТЕЧКА: Обнаружена утечка DNS данных! "
                    "Проверьте и переконфигурируйте ваш VPN клиент."
                )
        elif vpn.vpn_status == VPNStatus.POSSIBLE:
            recommendations.append(
                "⚠️  ВОЗМОЖЕН VPN: Обнаружены признаки VPN, но уверенность средняя. "
                "Проверьте вашу сетевую конфигурацию."
            )

        # Дополнительные рекомендации
        if vpn.confidence > 0.7 and nat.nat_type in [NATType.SYMMETRIC, NATType.STRICT]:
            recommendations.append(
                "✓ VPN + сложный NAT: Комбинация может снизить скорость. "
                "Используйте VPN с поддержкой UDP для лучшей производительности."
            )

        # Рекомендации по DNS
        public_dns = [
            "8.8.8.8", "8.8.4.4", "1.1.1.1", "9.9.9.9"
        ]
        using_public_dns = any(dns in public_dns for dns in vpn.dns_servers)

        if using_public_dns and vpn.vpn_status == VPNStatus.NOT_DETECTED:
            recommendations.append(
                "ℹ️  ПУБЛИЧНЫЙ DNS: Вы используете публичный DNS сервер. "
                "Рассмотрите использование DNS сервера вашего ISP или приватного DNS."
            )

        return "\n".join(f"  {rec}" for rec in recommendations) if recommendations else "  ✓ Всё в норме!"


# ============================================================================
# Фабрика для создания сервиса
# ============================================================================

class DiagnosticServiceFactory:
    """Фабрика для создания диагностического сервиса"""

    @staticmethod
    def create_service() -> DiagnosticService:
        """Создать полнофункциональный диагностический сервис"""

        # Создаём компоненты
        ip_provider: IPProvider = LocalIPProvider()
        stun_client = SimplSTUNClient(ip_provider)

        nat_analyzer: NATAnalyzer = NATAnalyzerImpl(stun_client, ip_provider)
        vpn_detector: VPNDetector = AdvancedVPNDetector(ip_provider)

        return DiagnosticService(nat_analyzer, vpn_detector)


# ============================================================================
# Главная функция
# ============================================================================

def main():
    """Главная функция"""

    try:
        print("\n" + "█" * 75)
        print("█" + " " * 73 + "█")
        print("█" + "  NAT & VPN DIAGNOSTIC TOOL v2.0".center(73) + "█")
        print("█" + "  Advanced Detection with Multiple Analysis Methods".center(73) + "█")
        print("█" + " " * 73 + "█")
        print("█" * 75)

        # Создаём сервис
        service = DiagnosticServiceFactory.create_service()

        # Запускаем диагностику
        report = service.run_diagnostics()

        # Выводим отчёт
        formatted_report = ReportFormatter.format_report(report)
        print(formatted_report)

        # Выводим рекомендации
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("💡 РЕКОМЕНДАЦИИ")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(RecommendationEngine.get_recommendations(report))
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# Демонстрация с тестовыми данными (без VPN)
# ============================================================================

class MockIPProviderNoVPN(IPProvider):
    """Мок для тестирования без VPN"""

    def get_external_ip(self) -> str:
        return "203.0.113.42"

    def get_internal_ip(self) -> str:
        return "192.168.1.100"


# ============================================================================
# Демонстрация с тестовыми данными (с VPN)
# ============================================================================

class MockIPProviderWithVPN(IPProvider):
    """Мок для тестирования с VPN"""

    def get_external_ip(self) -> str:
        return "185.220.101.10"  # Другая подсеть - признак VPN

    def get_internal_ip(self) -> str:
        return "10.8.0.5"  # Типичная VPN подсеть


def demo_no_vpn():
    """Демонстрация без VPN"""
    print("\n" + "="*75)
    print("ТЕСТ 1: БЕЗ VPN")
    print("="*75)

    ip_provider = MockIPProviderNoVPN()
    stun_client = SimplSTUNClient(ip_provider)
    nat_analyzer = NATAnalyzerImpl(stun_client, ip_provider)
    vpn_detector = AdvancedVPNDetector(ip_provider)

    service = DiagnosticService(nat_analyzer, vpn_detector)
    report = service.run_diagnostics()

    print(ReportFormatter.format_report(report))
    print("\n💡 РЕКОМЕНДАЦИИ:")
    print(RecommendationEngine.get_recommendations(report))


def demo_with_vpn():
    """Демонстрация с VPN"""
    print("\n" + "="*75)
    print("ТЕСТ 2: С VPN")
    print("="*75)

    ip_provider = MockIPProviderWithVPN()
    stun_client = SimplSTUNClient(ip_provider)
    nat_analyzer = NATAnalyzerImpl(stun_client, ip_provider)
    vpn_detector = AdvancedVPNDetector(ip_provider)

    service = DiagnosticService(nat_analyzer, vpn_detector)
    report = service.run_diagnostics()

    print(ReportFormatter.format_report(report))
    print("\n💡 РЕКОМЕНДАЦИИ:")
    print(RecommendationEngine.get_recommendations(report))


if __name__ == "__main__":
    # Выберите один из вариантов:

    # Вариант 1: Реальная диагностика (может потребовать прав администратора)
    main()

    # Вариант 2: Демонстрация без VPN (раскомментируйте)
    # demo_no_vpn()

    # Вариант 3: Демонстрация с VPN (раскомментируйте)
    demo_with_vpn()

