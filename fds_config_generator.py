#!/usr/bin/env python3
"""
Gerador de arquivos XML para sistemas FDS (Frauscher Diagnostic System)
Gera arquivos FdsConfig.xml e Trackplan.xml baseado em configurações
"""

import xml.etree.ElementTree as ET
import xml.dom.minidom
# Import utilitário de normalização com fallback para execução direta
try:
    from .xml_utils import normalize_trackplan_order
except Exception:
    from xml_utils import normalize_trackplan_order
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class NetworkConfig:
    """Configurações de rede para o sistema FDS"""
    ip_net1: str
    mask_net1: str = "255.255.255.0"
    ip_net2: str = "192.168.0.12"
    mask_net2: str = "255.255.255.0"
    gateway_net1: str = "192.168.0.1"
    gateway_net2: str = "192.168.0.1"
    default_gateway: str = "Gateway2"
    udp_port: int = 45
    time_server1: str = "192.168.103.172"
    time_server2: str = "192.168.103.173"
    
    def __post_init__(self):
        if self.gateway_net1 is None:
            self.gateway_net1 = self.ip_net1

@dataclass
class ElementConfig:
    """Configuração de um elemento do sistema"""
    element_id: int
    element_type: str  # ComMaster, Aeb, CountingHead, TrackSection1, TrackSection2
    element_assignment: str
    element_trackplan_id: str = None
    
    def __post_init__(self):
        if self.element_trackplan_id is None:
            # Prefixos por tipo + ID base com padding de 3 dígitos (ex.: 1 -> 001)
            prefix_map = {
                'ComMaster': '0',
                'Aeb': '1',
                'CountingHead': '2',
                'TrackSection1': '3',
                'TrackSection2': '4',
                'Ioexb': '5',
            }
            prefix = prefix_map.get(self.element_type, '0')
            try:
                base_id = int(self.element_id)
            except Exception:
                # Fallback robusto para casos inesperados
                base_id = int(str(self.element_id).strip() or 0)
            self.element_trackplan_id = f"{prefix}{base_id:03d}"

@dataclass
class StationConfig:
    """Configuração da estação"""
    config_version: str
    station_name: str
    fds_name: str
    timezone: str

@dataclass
class TrackDimensions:
    """Dimensões da grade de trilhos"""
    width: int
    height: int

@dataclass
class RailElement:
    """Elemento de trilho"""
    id: int
    x: int
    y: int
    angle: int = 0
    mirror: int = 0
    rail_type: str = None  # SWITCH, etc.

@dataclass
class LinkElement:
    id: int
    x: int
    y: int
    angle: int = 0
    url: str = None

@dataclass
class SensorElement:
    """Elemento sensor"""
    id: int
    name: str
    ref_id: int
    x: int
    y: int
    angle: int = 0
    fma0: str = None
    fma1: str = None

@dataclass
class CrossingElement:
    """ Elemento cruzamento """
    id: int
    x: int
    y: int
    angle: int = 0

class FDSConfigGenerator:
    """Gerador principal dos arquivos XML FDS"""
    
    def __init__(self, network_config: NetworkConfig, station_config: StationConfig):
        self.network_config = network_config
        self.station_config = station_config
        self.elements: List[ElementConfig] = []
        
    def add_element(self, element: ElementConfig):
        """Adiciona um elemento à configuração"""
        self.elements.append(element)
        
    def add_com_master(self, element_id: int):
        """Adiciona um ComMaster"""
        element = ElementConfig(
            element_id=element_id,
            element_type="ComMaster",
            element_assignment=f"COM{element_id}"
        )
        self.add_element(element)
        return element
        
    def add_aeb_with_counting_head(self, element_id: int, track_sections: List[str] = None):
        """Adiciona um AEB com CountingHead e opcionalmente TrackSections"""
        # AEB
        aeb = ElementConfig(
            element_id=element_id,
            element_type="Aeb",
            element_assignment=f"AEB{element_id}"
        )
        self.add_element(aeb)
        
        # CountingHead
        counting_head = ElementConfig(
            element_id=element_id,
            element_type="CountingHead",
            element_assignment=f"ZP{element_id}"
        )
        self.add_element(counting_head)
        
        # TrackSections (se especificadas)
        if track_sections:
            for i, track_name in enumerate(track_sections, 1):
                track_section = ElementConfig(
                    element_id=element_id,
                    element_type=f"TrackSection{i}",
                    element_assignment=track_name
                )
                self.add_element(track_section)
        
        return aeb, counting_head
        
    def generate_fds_config_xml(self, fds_model="FDS101") -> str:
        """Gera o arquivo FdsConfig.xml"""
        root = ET.Element("FdsConfig")
        
        # Configuração básica
        ET.SubElement(root, "ConfigVersion").text = self.station_config.config_version
        ET.SubElement(root, "IpAddressNet1").text = self.network_config.ip_net1
        ET.SubElement(root, "MaskNet1").text = self.network_config.mask_net1
        ET.SubElement(root, "IpAddressNet2").text = self.network_config.ip_net2
        ET.SubElement(root, "MaskNet2").text = self.network_config.mask_net2
        ET.SubElement(root, "GatewayAddressNet1").text = self.network_config.gateway_net1
        ET.SubElement(root, "GatewayAddressNet2").text = self.network_config.gateway_net2
        if fds_model == "FDS102":
            ET.SubElement(root, "DefaultGateway").text = self.network_config.default_gateway
        ET.SubElement(root, "UdpPortFadc").text = str(self.network_config.udp_port)
        ET.SubElement(root, "TimeServer1").text = self.network_config.time_server1
        ET.SubElement(root, "TimeServer2").text = self.network_config.time_server2
        ET.SubElement(root, "StationName").text = self.station_config.station_name
        ET.SubElement(root, "FdsName").text = self.station_config.fds_name
        ET.SubElement(root, "TimeZone").text = self.station_config.timezone
        
        # Tema
        if fds_model == "FDS102":
            disablelogs = ET.SubElement(root, "DisableLogs")
            ET.SubElement(disablelogs, "WheelSpeed")
            ET.SubElement(disablelogs, "WheelDiameter")
            ET.SubElement(disablelogs, "InterlockingChannelWarning")

            theme = ET.SubElement(root, "Theme", Base="frauscher-light")
            colors = ET.SubElement(theme, "Colors")
            ET.SubElement(colors, "Color", Name="color-state-ok", Type="solid", Animation="no", Value="#47616e")
            ET.SubElement(colors, "Color", Name="color-state-offline", Type="solid", Animation="no", Value="#ffffff")
            ET.SubElement(colors, "Color", Name="color-state-desensitised", Type="solid", Animation="no", Value="#82a1ab")
            ET.SubElement(colors, "Color", Name="color-state-occupied", Type="solid", Animation="no", Value="#0097d5")
            ET.SubElement(colors, "Color", Name="color-state-warning", Type="solid", Animation="no", Value="#f9be04")
            ET.SubElement(colors, "Color", Name="color-state-wct", Type="solid", Animation="no", Value="#f9be04")
            ET.SubElement(colors, "Color", Name="color-state-error", Type="solid", Animation="flashing", Value="#e52027", Value2="#ffffff", Interval="500")
            ET.SubElement(colors, "Color", Name="color-background-track", Value="#dadee1")
        # Lista de elementos
        element_list = ET.SubElement(root, "ElementList")
        
        for element in self.elements:
            element_node = ET.SubElement(element_list, "Element")
            ET.SubElement(element_node, "ElementId").text = str(element.element_id)
            ET.SubElement(element_node, "ElementType").text = element.element_type
            ET.SubElement(element_node, "ElementAssignment").text = element.element_assignment
            ET.SubElement(element_node, "ElementTrackplanId").text = element.element_trackplan_id
            
            if element.element_type == "ComMaster" and fds_model == "FDS102":
                element_node = ET.SubElement(element_list, "Element")
                ET.SubElement(element_node, "ElementId").text = str(element.element_id)
                ET.SubElement(element_node, "ElementType").text = "ForwardingMaster"
                ET.SubElement(element_node, "ElementAssignment").text = element.element_assignment

            if element.element_type in ['TrackSection1', 'TrackSection2'] and fds_model == "FDS102":
                element_node = ET.SubElement(element_list, "Element")
                ET.SubElement(element_node, "ElementId").text = str(element.element_id)
                ET.SubElement(element_node, "ElementType").text = "TrackSectionExtern1" if element.element_type == 'TrackSection1' else "TrackSectionExtern2"
                ET.SubElement(element_node, "ElementAssignment").text = element.element_assignment
                ET.SubElement(element_node, "ElementTrackplanId").text = f'5{element.element_id}'

        return self._prettify_xml(root)
    
    def generate_trackplan_xml(self, track_dimensions: TrackDimensions, 
                              rails: List[RailElement],
                              links: List[LinkElement],
                              crossings: List[CrossingElement] = None,
                              sensors: List[SensorElement] = None) -> str:
        """Gera o arquivo Trackplan.xml"""
        root = ET.Element("Trackplan")
        root.set("name", self.station_config.station_name)
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:noNamespaceSchemaLocation", "Trackplan.xsd")
        
        # Configuração FDS
        fds = ET.SubElement(root, "Fds")
        fds.set("name", self.station_config.station_name)
        fds.set("ip", self.network_config.ip_net1)
        fds.set("netmask", self.network_config.mask_net1)
        fds.set("version", "1.0")
        
        # Estações
        stations = ET.SubElement(root, "Stations")
        ET.SubElement(stations, "ThisStation")
        
        # Grade de trilhos
        track = ET.SubElement(root, "Track")
        track.set("width", str(track_dimensions.width))
        track.set("height", str(track_dimensions.height))
        
        # Elementos de trilho
        for rail in rails:
            rail_element = ET.SubElement(track, "Rail")
            rail_element.set("id", str(rail.id))
            rail_element.set("angle", str(rail.angle))
            rail_element.set("mirror", str(rail.mirror))
            rail_element.set("x", str(rail.x))
            rail_element.set("y", str(rail.y))
            if rail.rail_type:
                rail_element.set("type", rail.rail_type)

        # Links
        for link in links:
            link_element = ET.SubElement(track, "Link")
            link_element.set("id", str(link.id))
            link_element.set("x", str(link.x))
            link_element.set("y", str(link.y))
            link_element.set("angle", str(link.angle))
            link_element.set("url", link.url)
        
        # Crossings
        for crossing in crossings:
            crossing_element = ET.SubElement(track, "Crossing")
            crossing_element.set("id", str(crossing.id))
            crossing_element.set("x", str(crossing.x))
            crossing_element.set("y", str(crossing.y))
            crossing_element.set("angle", str(crossing.angle))

        # Sensores
        for sensor in sensors:
            sensor_element = ET.SubElement(track, "Sensor")
            sensor_element.set("id", str(sensor.id))
            sensor_element.set("name", sensor.name)
            sensor_element.set("refId", str(sensor.ref_id))
            sensor_element.set("x", str(sensor.x))
            sensor_element.set("y", str(sensor.y))
            sensor_element.set("angle", str(sensor.angle))
            if sensor.fma0:
                sensor_element.set("fma0", sensor.fma0)
            if sensor.fma1:
                sensor_element.set("fma1", sensor.fma1)

        # Supervisores (vazio)
        ET.SubElement(root, "Supervisors")

        # Gabinetes (vazio por padrão)
        ET.SubElement(root, "Cubicles")

        # Harmonizar ordenação de nós para combinar com a saída do IntelligentXMLGenerator
        normalize_trackplan_order(root)

        return self._prettify_xml(root)
    
    def _prettify_xml(self, element: ET.Element) -> str:
        """Formata o XML de forma legível"""
        rough_string = ET.tostring(element, encoding='unicode')
        reparsed = xml.dom.minidom.parseString(rough_string)
        # Usar tabulação para combinar com o estilo de identação do Trackplan.xml de referência
        return reparsed.toprettyxml(indent="\t", encoding=None)


def normalize_trackplan_order(root: ET.Element) -> None:
    """Reordena nós do Trackplan para uma ordem consistente.

    - Dentro de <Track>: Rail → Sensor → Fma (ordem estável intra-grupo)
    - No nível raiz: Fds → Stations → Track → Supervisors → Cubicles (outros ao final)
    """
    try:
        # Ordenar filhos de <Track>
        track_elem = root.find("Track")
        if track_elem is not None:
            order_map = {"Rail": 0, "Sensor": 1, "Fma": 2}
            children = list(track_elem)
            children.sort(key=lambda el: order_map.get(el.tag, 99))
            track_elem[:] = children

        # Ordenar filhos do <Trackplan>
        root_order = {"Fds": 0, "Stations": 1, "Track": 2, "Supervisors": 3, "Cubicles": 4}
        root_children = list(root)
        root_children.sort(key=lambda el: root_order.get(el.tag, 99))
        root[:] = root_children
    except Exception:
        # Não interromper fluxo em caso de falhas de ordenação
        pass

# Exemplo de uso
def create_sample_iaa4_config():
    """Cria uma configuração de exemplo para IAA-4"""
    
    # Configuração de rede
    network = NetworkConfig(
        ip_net1="192.168.1.12",
        gateway_net1="192.168.1.1"
    )
    
    # Configuração da estação
    station = StationConfig(
        config_version="1.0",
        station_name="AREAIS",
        fds_name="ABRIGO 20 (IAA-4)",
        timezone="UTC-3"
    )
    
    # Gerador
    generator = FDSConfigGenerator(network, station)
    
    # Adicionar ComMaster
    generator.add_com_master(1381)
    
    # Adicionar AEBs com CountingHeads
    generator.add_aeb_with_counting_head(1255)
    generator.add_aeb_with_counting_head(1260)
    generator.add_aeb_with_counting_head(1265, ["2EAT", "4EAT"])
    generator.add_aeb_with_counting_head(1270, ["X1T", "X2T"])
    
    # Gerar FdsConfig.xml
    fds_config = generator.generate_fds_config_xml(fds_model="FDS101")
    
    # Configuração do track
    track_dims = TrackDimensions(width=9, height=4)
    
    # Trilhos de exemplo
    rails = [
        RailElement(id=7001, x=9, y=2, angle=180),
        RailElement(id=7002, x=8, y=2),
        RailElement(id=7003, x=7, y=2),
        RailElement(id=7004, x=6, y=2),
        RailElement(id=7005, x=5, y=2),
        RailElement(id=7006, x=4, y=2),
        RailElement(id=7007, x=3, y=2, angle=180, mirror=1, rail_type="SWITCH"),
    ]
    
    # Sensores de exemplo
    sensors = [
        SensorElement(id=21255, name="ZP1255", ref_id=11255, x=6, y=2, angle=180),
        SensorElement(id=21260, name="ZP1260", ref_id=11260, x=6, y=0, angle=180),
        SensorElement(id=21265, name="ZP1265", ref_id=11265, x=4, y=2, angle=180, fma0="31265", fma1="41265"),
        SensorElement(id=21270, name="ZP1270", ref_id=11270, x=4, y=0, angle=180, fma0="31270", fma1="41270"),
    ]
    links = [
        LinkElement(id=8001, x=2, y=3, angle=0, url="http://192.168.1.100"),
        LinkElement(id=8002, x=5, y=1, angle=90, url="http://192.168.1.101"),
    ]

    crossings = [
        CrossingElement(id=9001, x=3, y=2, angle=0),
    ]
    # Gerar Trackplan.xml
    trackplan = generator.generate_trackplan_xml(track_dims, rails, links, crossings, sensors)
    
    return fds_config, trackplan

if __name__ == "__main__":
    # Exemplo de uso
    fds_config, trackplan = create_sample_iaa4_config()
    
    # Salvar arquivos
    with open("FdsConfig_generated.xml", "w", encoding="utf-8") as f:
        f.write(fds_config)
    
    with open("Trackplan_generated.xml", "w", encoding="utf-8") as f:
        f.write(trackplan)
    
    print("Arquivos XML gerados com sucesso!")
    print("- FdsConfig_generated.xml")
    print("- Trackplan_generated.xml")
