#!/usr/bin/env python3
"""
Interface gráfica avançada para geração de configurações FDS
Inclui formulário para FdsConfig.xml e designer visual para Trackplan.xml
"""
## import ttkbootstrap as ttk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import sys
import copy
import tempfile
import zipfile
import traceback
import xml.etree.ElementTree as ET
import json
from pathlib import Path
from datetime import datetime
import ipaddress
from collections import Counter
import itertools

# Garantir que imports locais (ex.: fds_config_generator.py) funcionem mesmo quando o app
# é iniciado a partir de outro diretório.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# Imports opcionais de PIL
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Aviso: PIL/Pillow não encontrado - algumas funcionalidades podem estar limitadas")

# Imports opcionais com fallback
try:
    from fds_config_generator import *
except ImportError:
    print("Aviso: fds_config_generator não encontrado - usando implementação padrão")
    pass

# Garantir referências diretas às classes usadas do gerador para evitar erros de escopo local
try:
    # Importar explicitamente as classes necessárias
    from fds_config_generator import ElementConfig, FDSConfigGenerator, NetworkConfig, StationConfig
except Exception:
    # Se não disponível, definir como None; os pontos de uso tratarão a ausência
    ElementConfig = None
    FDSConfigGenerator = None
    NetworkConfig = None
    StationConfig = None

# === CLASSES AUXILIARES PARA TRACKPLAN ===

def _app_base_dir() -> Path:
    """
    Base para localizar arquivos quando:
    - rodando via PyInstaller: sys._MEIPASS
    - rodando via python: pasta do arquivo praxis.py
    """
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

def resource_path(*parts) -> str:
    """Caminho absoluto para um recurso empacotado (ou em dev)."""
    return str(_app_base_dir().joinpath(*parts))

class FDSModelSelectorDialog:
    """Diálogo para seleção do modo FDS (FDS101 ou FDS102)"""
    def __init__(self, parent, current_model='FDS101', show_remember=True):
        self.result = None
        self.remember = False
        self.parent = parent
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Praxis - Seleção de Modo")
        self.dialog.geometry("450x380")
        self.dialog.resizable(False, False)
        
        # Centralizar na tela
        self.dialog.update_idletasks()
        w, h = 450, 340
        x = (self.dialog.winfo_screenwidth() // 2) - (w // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (h // 2)
        self.dialog.geometry(f"{w}x{h}+{x}+{y}")
        
        # Configurar cores corporativas
        bg_color = '#f0f0f0'
        header_bg = '#1e3a5f'
        accent_color = '#FFFF00'
        
        self.dialog.configure(bg=bg_color)
        
        # Header corporativo
        header_frame = tk.Frame(self.dialog, bg=header_bg, height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        header_label = tk.Label(header_frame, text="Selecione o modo FDS",
                               font=('Segoe UI', 16, 'bold'),
                               bg=header_bg, fg=accent_color)
        header_label.pack(expand=True)
        
        # Conteúdo principal
        content_frame = tk.Frame(self.dialog, bg=bg_color, padx=30, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Texto informativo
        info_label = tk.Label(content_frame,
                             text="Escolha o modelo FDS para carregar o programa:",
                             font=('Segoe UI', 11),
                             bg=bg_color, fg='#333333')
        info_label.pack(pady=(0, 20))
        
        # Radio buttons
        self.selected_model = tk.StringVar(value=current_model)
        
        radio_frame = tk.Frame(content_frame, bg=bg_color)
        radio_frame.pack(pady=10)
        
        radio1 = tk.Radiobutton(radio_frame, text="FDS101",
                                variable=self.selected_model, value='FDS101',
                                font=('Segoe UI', 12),
                                bg=bg_color, activebackground=bg_color)
        radio1.pack(anchor=tk.W, pady=5)
        
        radio2 = tk.Radiobutton(radio_frame, text="FDS102",
                                variable=self.selected_model, value='FDS102',
                                font=('Segoe UI', 12),
                                bg=bg_color, activebackground=bg_color)
        radio2.pack(anchor=tk.W, pady=5)
        
        # Checkbox "Lembrar minha escolha" (opcional)
        if show_remember:
            self.remember_var = tk.BooleanVar(value=False)
            remember_check = tk.Checkbutton(content_frame,
                                           text="Lembrar minha escolha",
                                           variable=self.remember_var,
                                           font=('Segoe UI', 9),
                                           bg=bg_color, activebackground=bg_color)
            remember_check.pack(pady=(10, 0))
        else:
            self.remember_var = tk.BooleanVar(value=False)
        
        # Botões
        button_frame = tk.Frame(content_frame, bg=bg_color)
        button_frame.pack(pady=(20, 0))
        
        confirm_btn = tk.Button(button_frame, text="Confirmar",
                               command=self.confirm,
                               font=('Segoe UI', 10, 'bold'),
                               bg='#073359', fg='#FFFF00',
                               activebackground='#093773',
                               activeforeground='#FFFF00',
                               width=12, height=1,
                               relief=tk.RAISED, bd=2)
        confirm_btn.pack(side=tk.LEFT, padx=5)
        
        cancel_btn = tk.Button(button_frame, text="Cancelar",
                              command=self.cancel,
                              font=('Segoe UI', 10),
                              bg='#cccccc', fg='#333333',
                              activebackground='#bbbbbb',
                              width=12, height=1,
                              relief=tk.RAISED, bd=2)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Bind ESC para cancelar
        self.dialog.bind('<Escape>', lambda e: self.cancel())
        self.dialog.bind('<Return>', lambda e: self.confirm())
        
        # Protocolo de fechamento
        self.dialog.protocol("WM_DELETE_WINDOW", self.cancel)
        
    def confirm(self):
        """Confirma a seleção"""
        self.result = self.selected_model.get()
        self.remember = self.remember_var.get()
        self.dialog.destroy()
        
    def cancel(self):
        """Cancela o diálogo"""
        self.result = None
        self.dialog.destroy()
        
    def show(self):
        """Mostra o diálogo e aguarda resposta"""
        # Garantir que a janela está visível
        self.dialog.deiconify()
        self.dialog.lift()
        self.dialog.focus_force()
        
        # Processar eventos pendentes
        self.parent.update()
        
        # Aguardar até a janela ser destruída
        try:
            self.dialog.wait_window(self.dialog)
        except tk.TclError:
            # Janela já foi destruída
            pass
        
        return self.result, self.remember


class TrackplanElementData:
    """Classe base para dados de elementos do trackplan"""
    def __init__(self, xml_element):
        self.xml_element = xml_element
        self.x = int(xml_element.get("x", 0))
        self.y = int(xml_element.get("y", 0))
        self.angle = int(xml_element.get("angle", 0))

class RailData(TrackplanElementData):
    """Dados específicos de rail/switch"""
    def __init__(self, xml_element):
        super().__init__(xml_element)
        self.rail_id = xml_element.get("id")
        self.mirror = int(xml_element.get("mirror", 0))
        self.rail_type = xml_element.get("type", "RAIL")

class LinkData(TrackplanElementData):
    """Dados específicos de link"""
    def __init__(self, xml_element):
        super().__init__(xml_element)
        self.link_id = xml_element.get("id")
        self.url = xml_element.get("url")

class SensorData(TrackplanElementData):
    """Dados específicos de sensor"""
    def __init__(self, xml_element):
        super().__init__(xml_element)
        self.sensor_id = xml_element.get("id")
        self.name = xml_element.get("name", f"S{self.sensor_id}")
        self.ref_id = xml_element.get("refId", self.sensor_id)
        # Preservar associações vindas do XML (podem existir isoladamente)
        self.fma0 = xml_element.get("fma0")
        self.fma1 = xml_element.get("fma1")

class CrossingData(TrackplanElementData):
    """Dados específicos do cruzamento"""
    def __init__(self, xml_element):
        super().__init__(xml_element)
        self.crossing_id = xml_element.get("id")
        self.paths = []
        for path in xml_element.findall(".//Path"):
            self.paths.append({
                "from": path.get("from"),
                "to": path.get("to"),
            })

class FMAData(TrackplanElementData):
    """Dados específicos de FMA"""
    def __init__(self, xml_element):
        super().__init__(xml_element)
        self.fma_id = xml_element.get("id")
        self.name = xml_element.get("name", f"FMA{self.fma_id}")
        self.ref_id = xml_element.get("refId", "")

        # Carregar associações
        self.associated_sensors = []
        self.associated_rails = []

        # Carregar trilhos/links/crossings associados
        rails_refs = xml_element.findall(".//Rails/Ref")
        for rail_ref in rails_refs:
            rail_id = rail_ref.get("refId")
            if not rail_id:
                continue

            item = {"refId": str(rail_id).strip()}

            from_attr = rail_ref.get("from")
            to_attr = rail_ref.get("to")

            if from_attr is not None and str(from_attr).strip() != "":
                item["from"] = str(from_attr).strip()
            if to_attr is not None and str(to_attr).strip() != "":
                item["to"] = str(to_attr).strip()

            # Se veio from/to no Ref, tratar como crossing associado
            if "from" in item or "to" in item:
                item["type"] = "crossing"

            self.associated_rails.append(item)

        sensor_nodes = []
        sensor_nodes.extend(xml_element.findall(".//Sensors/Ref"))
        sensor_nodes.extend(xml_element.findall(".//Sensors/Sensor"))

        for sref in sensor_nodes:
            sid = sref.get("refId") or sref.get("id")
            if not sid:
                continue

            # Alguns XMLs usam "fmaPosition", outros "position"
            pos = (sref.get("fmaPosition") or sref.get("position") or "").strip().lower()
            if pos not in ("left", "right"):
                pos = "right"

            self.associated_sensors.append({
                "refId": str(sid),
                "fmaPosition": pos
            })

# === FUNÇÕES DE PERSISTÊNCIA DE CONFIGURAÇÃO ===

def load_user_config():
    """Carrega configurações do usuário do arquivo JSON"""
    config_file = 'praxis_config.json'
    default_config = {
        'fds_model': 'FDS101',
        'remember': False
    }
    
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                return {**default_config, **loaded_config}
        else:
            return default_config
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Erro ao carregar configuração: {e}")
        return default_config

def save_user_config(fds_model, remember):
    """Salva configurações do usuário no arquivo JSON"""
    config_file = 'praxis_config.json'
    config = {
        'fds_model': fds_model,
        'remember': remember
    }
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        print(f"Configuração salva: {config}")  # Debug
    except Exception as e:
        print(f"Erro ao salvar configuração: {e}")

class TrackplanXMLData:
    """Container para todos os dados do XML do trackplan"""
    def __init__(self, root, filename):
        self.root = root
        self.filename = filename
        
        # Extrair elementos
        self.rails = [RailData(rail) for rail in root.findall(".//Rail")]
        self.links = [LinkData(link) for link in root.findall(".//Link")]
        self.sensors = [SensorData(sensor) for sensor in root.findall(".//Sensor")]
        self.fmas = [FMAData(fma) for fma in root.findall(".//Fma")]
        self.crossings = [CrossingData(crossing) for crossing in root.findall(".//Crossing")]
        
        # Criar dicionários para acesso rápido
        self.rails_dict = {rail.rail_id: rail.xml_element for rail in self.rails if rail.rail_id}
        self.links_dict = {link.link_id: link.xml_element for link in self.links if link.link_id}
        self.sensors_dict = {sensor.sensor_id: sensor.xml_element for sensor in self.sensors if sensor.sensor_id}
        self.fmas_dict = {fma.fma_id: fma.xml_element for fma in self.fmas if fma.fma_id}
        self.crossing_dict = {crossing.crossing_id: crossing.xml_element for crossing in self.crossings if crossing.crossing_id}

class IntelligentXMLGenerator:
    """Classe para geração inteligente de XML"""
    
    def __init__(self, elements_list, form_fields=None, cubicles_data=None):
        self.elements = elements_list or []
        self.form_fields = form_fields or {}
        self.cubicles_data = cubicles_data or []
        
        # Validar entrada
        if not isinstance(self.elements, list):
            raise ValueError("elements_list deve ser uma lista")

    def generate_smart_xml(self, filename, fds_model="FDS101", next_element_id=7000):
        """Gera XML inteligente criando rails automaticamente para sensores/FMAs durante o export"""
        try:
            # Criar estrutura XML básica do Trackplan
            trackplan_root = ET.Element("Trackplan")
            trackplan_root.set("name", self.form_fields.get("StationName", tk.StringVar()).get().strip())
            trackplan_root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
            trackplan_root.set("xsi:noNamespaceSchemaLocation", "Trackplan.xsd")
            
            selected_network = str(self._get_form_value("TrackplanNetwork", "IP Rede1")).strip().lower()
            use_net2 = "2" in selected_network

            ip_field = "IpAddressNet2" if use_net2 else "IpAddressNet1"
            mask_field = "MaskNet2" if use_net2 else "MaskNet1"
            ip_default = "192.168.0.12" if use_net2 else "192.168.1.12"
            mask_default = "255.255.255.0"

            # Informações do FDS
            fds_elem = ET.SubElement(trackplan_root, "Fds")
            fds_elem.set("name", self._get_form_value("FdsName", "ABRIGO AREAIS"))
            fds_elem.set("ip", self._get_form_value(ip_field, ip_default))
            fds_elem.set("netmask", self._get_form_value(mask_field, mask_default))
            fds_elem.set("version", self._get_form_value("ConfigVersion", "1.0"))
            
            # Estações
            stations_elem = ET.SubElement(trackplan_root, "Stations")
            this_station_elem = ET.SubElement(stations_elem, "ThisStation")

            # Track (grade)
            track_elem = ET.SubElement(trackplan_root, "Track")
            track_elem.set("width", self._get_form_value("width_var", "71"))
            track_elem.set("height", self._get_form_value("height_var", "16"))
            
            # Coletar elementos por tipo
            real_rails = [e for e in self.elements if e.get("type") == "rail" and not e.get("auto_rail") and e.get("rail_type") != "SWITCH"]
            switches = [e for e in self.elements if e.get("type") == "switch" or (e.get("type") == "rail" and e.get("rail_type") == "SWITCH")]
            sensors = [e for e in self.elements if e.get("type") == "sensor"]
            fmas = [e for e in self.elements if e.get("type") == "fma"]
            links = [e for e in self.elements if e.get("type") == "link"]
            crossings = [e for e in self.elements if e.get("type") == "crossing"]

            real_rail_ids_in_xml = {str(r.get("id")) for r in real_rails} | {str(s.get("id")) for s in switches} | {str(l.get("id")) for l in links} | {str(c.get("id")) for c in crossings}

            element_type_by_id = {}
            element_crossing_by_id = {}

            for element in self.elements:
                eid = str(element.get("id", "")).strip()
                if not eid:
                    continue
                element_type_by_id[eid] = element.get("type")
                if element.get("type") == "crossing":
                    element_crossing_by_id[eid] = element

            # Criar dicionário de FMAs para busca rápida
            fmas_by_ref_id = {}
            for fma in fmas:
                fma_ref_id = str(fma.get("ref_id", ""))
                fma_id_str = str(fma.get("id", ""))
                if fma_ref_id and fma_id_str:
                    # Mapear como lista para suportar múltiplas FMAs com mesmo ref_id
                    if fma_ref_id not in fmas_by_ref_id:
                        fmas_by_ref_id[fma_ref_id] = []
                    fmas_by_ref_id[fma_ref_id].append(fma)
                
            # IDs únicos para rails automáticos
            created_auto_rails = {}  # posição -> rail_id
            
            for link in links:
                link_elem = ET.SubElement(track_elem, "Link")
                link_elem.set("id", str(link.get("id")))
                link_elem.set("url", str(link.get("url")))
                link_elem.set("angle", str(link.get("angle")))
                link_elem.set("x", str(link.get("x")))
                link_elem.set("y", str(link.get("y")))

            for crossing in crossings:
                crossing_elem = ET.SubElement(track_elem, "Crossing")
                crossing_elem.set("id", str(crossing.get("id")))
                crossing_elem.set("angle", str(crossing.get("angle")))
                crossing_elem.set("x", str(crossing.get("x")))
                crossing_elem.set("y", str(crossing.get("y")))

            # Adicionar rails reais ao XML
            for rail in real_rails:
                rail_xml = ET.SubElement(track_elem, "Rail")
                rail_xml.set("id", str(rail.get("id", "")))
                rail_xml.set("angle", str(rail.get("angle", 0)))
                rail_xml.set("mirror", str(rail.get("mirror", 0)))
                rail_xml.set("x", str(rail.get("x", 0)))
                rail_xml.set("y", str(rail.get("y", 0)))

            # Adicionar switches como Rails com type="SWITCH"
            for switch in switches:
                rail_xml = ET.SubElement(track_elem, "Rail")
                rail_xml.set("id", str(switch.get("id", "")))
                rail_xml.set("type", "SWITCH")
                rail_xml.set("angle", str(switch.get("angle", 0)))
                rail_xml.set("mirror", str(switch.get("mirror", 0)))
                rail_xml.set("x", str(switch.get("x", 0)))
                rail_xml.set("y", str(switch.get("y", 0)))
        
            # Processar sensores - IntelligentXMLGenerator (FUNÇÃO 1)
            sensors_created = 0
            
            for sensor in sensors:
                # Verificar se precisa de rail automático
                position = (sensor.get("x"), sensor.get("y"))
                rail_at_position = self._find_real_rail_at_position(real_rails + switches, position)
                
                # Adicionar sensor ao XML
                sensor_xml = ET.SubElement(track_elem, "Sensor")
                sensor_id = str(sensor.get("id", ""))
                sensor_xml.set("id", sensor_id)
                sensor_xml.set("angle", str(sensor.get("angle", 0)))
                sensor_xml.set("x", str(sensor.get("x", 0)))
                sensor_xml.set("y", str(sensor.get("y", 0)))
                sensors_created += 1
                
                # Adicionar name e refId baseado no ID do sensor
                if sensor_id and sensor_id.startswith("2") and len(sensor_id) > 1:  # Validação melhorada
                    ref_id_base = sensor_id[1:]  # Remove o "2" inicial para obter o refId base
                    sensor_name = f"ZP{ref_id_base}"
                    ref_id = f"1{ref_id_base}"  # RefId formato: 1XXXX
                    
                    sensor_xml.set("name", sensor_name)
                    sensor_xml.set("refId", ref_id)
                    
                    fma0_id = sensor.get("fma0")
                    fma1_id = sensor.get("fma1")

                    if not fma0_id and not fma1_id:
                        pass

                    if fma0_id:
                        sensor_xml.set("fma0", str(fma0_id))
                    if fma1_id:
                        sensor_xml.set("fma1", str(fma1_id))
                    
                # Se não há rail real na posição, criar rail automático
                if not rail_at_position and position not in created_auto_rails:
                    # Usar a configuração mais completa (auto_rail_config) que inclui mirror
                    sensor_angle = sensor.get("angle", 0)
                    rail_angle, rail_mirror = self._get_rail_config_for_sensor(sensor_angle)
                    
                    auto_rail_xml = ET.SubElement(track_elem, "Rail")
                    auto_rail_xml.set("id", str(next_element_id))
                    auto_rail_xml.set("angle", str(rail_angle))
                    auto_rail_xml.set("mirror", str(rail_mirror))
                    auto_rail_xml.set("x", str(sensor.get("x", 0)))
                    auto_rail_xml.set("y", str(sensor.get("y", 0)))
                    
                    created_auto_rails[position] = next_element_id
                    if ((next_element_id + 1) == 8000):
                        next_element_id = 71000
                    else:
                        next_element_id += 1

            for i, fma in enumerate(fmas):
                fma_xml = ET.SubElement(track_elem, "Fma")
                fma_xml.set("id", str(fma.get("id", "")))
                fma_xml.set("name", fma.get("name", f"FMA{fma.get('id')}"))
                fma_xml.set("angle", str(fma.get("angle", 0)))
                fma_xml.set("x", str(fma.get("x", 0)))
                fma_xml.set("y", str(fma.get("y", 0)))
                
                # Adicionar refId para FMAs baseado no ID
                fma_id_str = str(fma.get("id", "")).strip()
                if fma_id_str and len(fma_id_str) > 1:
                    if fma_id_str[0] in ("3","4"):
                        base = fma_id_str[1:]
                        fma_xml.set("refId", f"2{base}")
                    elif fma.get("ref_id"):
                        fma_xml.set("refId", str(fma.get("ref_id")))
                else:
                    print(f"    ❌ FMA sem ID válido: {fma_id_str}")
 
                # DENTRO DA FMA: Rails primeiro, Sensors depois
                rails_refs_xml = ET.SubElement(fma_xml, "Rails")
                added_ref_ids = set()

                # Adicionar somente rails associados que EXISTEM no XML (reais)
                if fma.get("associated_rails"):
                    for rail_ref in fma["associated_rails"]:
                        rid = str(rail_ref.get("refId", "")).strip()
                        if not rid:
                            continue

                        rtype = rail_ref.get("type") or element_type_by_id.get(rid)
                        attrs = {"refId": rid}

                        if rtype == "crossing":
                            crossing_source = element_crossing_by_id.get(rid, {})
                            from_value = rail_ref.get("from")
                            to_value = rail_ref.get("to")

                            if from_value is None:
                                from_value = crossing_source.get("from")
                            if to_value is None:
                                to_value = crossing_source.get("to")

                            if from_value is not None:
                                attrs["from"] = str(from_value)
                            if to_value is not None:
                                attrs["to"] = str(to_value)

                        if rid in real_rail_ids_in_xml or rtype == "crossing":
                            if rid not in added_ref_ids:
                                ET.SubElement(rails_refs_xml, "Ref", attrs)
                                added_ref_ids.add(rid)

                # Adicionar rail automático se FMA está numa posição sem rail real
                fma_position = (fma.get("x"), fma.get("y"))
                real_here = self._find_real_rail_at_position(real_rails + switches + crossings, fma_position)

                # FMAs sempre devem ter um rail, mesmo que não exista sensor na mesma posição
                if not real_here:
                    if fma_position not in created_auto_rails:
                        rail_angle, rail_mirror = self._get_rail_config_for_fma(fma.get("angle", 0))
                        auto_rail_xml = ET.SubElement(track_elem, "Rail")
                        auto_rail_xml.set("id", str(next_element_id))
                        auto_rail_xml.set("angle", str(rail_angle))
                        auto_rail_xml.set("mirror", str(rail_mirror))
                        auto_rail_xml.set("x", str(fma.get("x", 0)))
                        auto_rail_xml.set("y", str(fma.get("y", 0)))
                        created_auto_rails[fma_position] = next_element_id
                        if ((next_element_id + 1) == 8000):
                            next_element_id = 71000
                        else:
                            next_element_id += 1

                    auto_id = str(created_auto_rails[fma_position])
                    if auto_id not in added_ref_ids:
                        ET.SubElement(rails_refs_xml, "Ref", {"refId": auto_id})
                        added_ref_ids.add(auto_id)
                else:
                    rid = str(real_here.get("id"))
                    if rid and rid not in added_ref_ids:
                        ref_attrs = {"refId": rid}
                        if real_here.get("type") == "crossing":
                            crossing_source = element_crossing_by_id.get(rid, {})
                            if crossing_source.get("from") is not None:
                                ref_attrs["from"] = str(crossing_source.get("from"))
                            if crossing_source.get("to") is not None:
                                ref_attrs["to"] = str(crossing_source.get("to"))
                        ET.SubElement(rails_refs_xml, "Ref", ref_attrs)
                        added_ref_ids.add(rid)

                if fma_position in created_auto_rails and not any(ref.get("refId") == str(created_auto_rails[fma_position]) for ref in rails_refs_xml.findall("Ref")):
                    ET.SubElement(rails_refs_xml, "Ref", {"refId": str(created_auto_rails[fma_position])})

                # Processar sensores associados DEPOIS dos rails (dentro da FMA)
                if fma.get("associated_sensors"):
                    sensors_refs_xml = ET.SubElement(fma_xml, "Sensors")
                    for sensor_ref in fma["associated_sensors"]:
                        sid = sensor_ref and sensor_ref.get("refId")
                        if sid:
                            ET.SubElement(sensors_refs_xml, "Ref", {
                                "refId": str(sid),
                                "fmaPosition": sensor_ref.get("fmaPosition", "right")
                            })

            
            # === INTEGRAR CUBICLES ===
            if self.cubicles_data and len(self.cubicles_data) > 0:
                cubicles_elem = ET.SubElement(trackplan_root, "Cubicles")

                for cubicle in self.cubicles_data:
                    cubicle_xml = ET.SubElement(cubicles_elem, "Cubicle")
                    cubicle_xml.set("height", str(cubicle.get("height", "1")))
                    cubicle_xml.set("id", str(cubicle.get("id", "")))
                    cubicle_xml.set("name", str(cubicle.get("name", "")))

                    # Processar Rack
                    rack = cubicle.get('rack', {})
                    if rack:
                        rack_xml = ET.SubElement(cubicle_xml, "Rack")
                        rack_xml.set("id", str(rack.get("id", "")))

                        # Processar Backplane
                        bp = rack.get('bp', {})
                        if bp:
                            bp_xml = ET.SubElement(rack_xml, "Bp")
                            bp_xml.set("id", str(bp.get("id", "")))
                            bp_xml.set("size", str(bp.get("size", "13")))
                            bp_xml.set("startSlot", str(bp.get("startSlot", "1")))

                            # Processar slots ordenados
                            slots = bp.get('slots', {})
                            if slots:
                                sorted_slots = sorted(slots.items(), key=lambda x: int(x[0]))

                                for slot_id, slot in sorted_slots:
                                    slot_type = slot.get('type', 'EmptySlot')
                                    slot_xml_id = slot.get('id', '')

                                    if slot_type == 'Psc':
                                        slot_xml = ET.SubElement(bp_xml, "Psc")
                                        slot_xml.set("id", str(slot_xml_id))
                                        slot_xml.set("slotId", str(slot_id))

                                    elif slot_type == 'Com':
                                            slot_xml = ET.SubElement(bp_xml, "Com")
                                            slot_xml.set("id", str(slot_xml_id))
                                            slot_xml.set("canId", str(slot.get("canId", "")))
                                            slot_xml.set("type", "COM_FSE")
                                            slot_xml.set("redundant", "NORMAL")
                                            slot_xml.set("name", str(slot.get("name", "")))
                                            slot_xml.set("slotId", str(slot_id))
                                            # Adicionar texto vazio para forçar tag de fechamento separada
                                            slot_xml.text = "\n\t\t\t\t\t"

                                    elif slot_type == 'Aeb':
                                        slot_xml = ET.SubElement(bp_xml, "Aeb")
                                        slot_xml.set("id", str(slot_xml_id))
                                        slot_xml.set("name", str(slot.get("name", "")))
                                        slot_xml.set("canId", str(slot.get("canId", "")))
                                        slot_xml.set("refId", str(slot.get("refId", "")))
                                        slot_xml.set("slotId", str(slot_id))

                                    elif slot_type == 'IoExb':
                                        slot_xml = ET.SubElement(bp_xml, "IoExb")
                                        slot_xml.set("id", str(slot_xml_id))
                                        slot_xml.set("name", "IO-EXB")
                                        slot_xml.set("refId", str(slot.get("refId", "")))
                                        slot_xml.set("slotId", str(slot_id))

                                        # Nova seção FDS102
                                        if fds_model == "FDS102":
                                            slot_xml_ext = ET.SubElement(slot_xml, "TrackSectionExtern")
                                            _slot_xml1 = ET.SubElement(slot_xml_ext, "FmaExtern")
                                            _slot_xml1.set("refId", f'3{slot_xml_id[1:]}')
                                            _slot_xml2 = ET.SubElement(slot_xml_ext, "FmaExtern")
                                            _slot_xml2.set("refId", f'4{slot_xml_id[1:]}')

                                    elif slot_type == 'EmptySlot':
                                        slot_xml = ET.SubElement(bp_xml, "EmptySlot")
                                        slot_xml.set("id", str(slot_xml_id))
                                        slot_xml.set("slotId", str(slot_id))
            else:
                print("Nenhum cubicle encontrado para integrar ao Trackplan XML")
        
            # Garantir seções raiz (Supervisors e Cubicles) e ordenação consistente dos nós
            try:
                # Adicionar Supervisors vazio se ausente
                if trackplan_root.find("Supervisors") is None:
                    ET.SubElement(trackplan_root, "Supervisors")

                # Adicionar Cubicles vazio se ausente (não duplica se já criados acima)
                if trackplan_root.find("Cubicles") is None:
                    ET.SubElement(trackplan_root, "Cubicles")

                # Ordenar filhos de <Track> por grupos: Rail → Sensor → Fma, preservando ordem relativa dentro do grupo
                track_elem = trackplan_root.find("Track")
                if track_elem is not None:
                    rails_and_links = [el for el in track_elem if el.tag in ("Rail", "Link", "Crossing")]
                    sensors = [el for el in track_elem if el.tag == "Sensor"]
                    fmas = [el for el in track_elem if el.tag == "Fma"]
                    # Ordenar rails e links por id crescente
                    def get_id(el):
                        try:
                            return int(el.get("id", "0"))
                        except Exception:
                            return 0

                    rails_and_links.sort(key=get_id)

                    # Recriar lista de filhos: rails+links juntos, depois sensors, depois fmas
                    track_elem[:] = rails_and_links + sensors + fmas

                # Ordenar filhos de <Trackplan>: Fds → Stations → Track → Supervisors → Cubicles (outros ao final)
                root_order = {"Fds": 0, "Stations": 1, "Track": 2, "Supervisors": 3, "Cubicles": 4}
                root_children = list(trackplan_root)
                root_children.sort(key=lambda el: root_order.get(el.tag, 99))
                trackplan_root[:] = root_children
            except Exception as _e:
                print(f"Aviso: falha ao ordenar nós do XML: {_e}")

            # Salvar XML com pretty-print usando tabulação (compatível com estilo de referência)
            try:
                from xml.dom import minidom
                rough = ET.tostring(trackplan_root, encoding='utf-8')
                reparsed = minidom.parseString(rough)
                pretty_bytes = reparsed.toprettyxml(indent="\t", encoding="utf-8")
                with open(filename, "wb") as f:
                    f.write(pretty_bytes)
            except Exception:
                # Fallback para identação nativa, caso minidom falhe
                tree = ET.ElementTree(trackplan_root)
                try:
                    ET.indent(tree, space="\t", level=0)
                except Exception:
                    pass
                tree.write(filename, encoding='utf-8', xml_declaration=True)

            return filename
        
        except Exception as e:
            print(f"Erro ao gerar XML inteligente: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def _get_form_value(self, field_name, default_value):
        """Obtém valor do formulário ou usa default"""
        try:
            if field_name in self.form_fields:
                field = self.form_fields[field_name]
                if hasattr(field, 'get'):
                    value = field.get()
                    return value if value else default_value
                return str(field) if field else default_value
            return default_value
        except (AttributeError, ValueError, TypeError) as e:
            print(f"Erro ao obter valor do campo {field_name}: {e}")
            return default_value
    
    def _find_real_rail_at_position(self, real_rails, position):
        """Encontra rail real na posição especificada"""
        if not position or len(position) != 2:
            return None
            
        x, y = position
        try:
            for rail in real_rails:
                rail_x = rail.get("x")
                rail_y = rail.get("y")
                if rail_x == x and rail_y == y:
                    return rail
        except (TypeError, AttributeError) as e:
            print(f"Erro ao buscar rail na posição {position}: {e}")
        
        return None

    def _get_rail_config_for_sensor(self, sensor_angle):
        """Obtém configuração completa de rail (ângulo, mirror) para sensor usando auto_rail_config"""
        # Configuração detalhada com mirrors para sensores
        sensor_config = {
            0: (0, 0),       # Sensor 0° → Rail 0° mirror 0
            45: (270, 0),    # Sensor 45° → Rail 270° mirror 0
            90: (180, 0),    # Sensor 90° → Rail 180° mirror 0
            135: (270, 1),   # Sensor 135° → Rail 270° mirror 1
            180: (0, 0),     # Sensor 180° → Rail 0° mirror 0
            225: (270, 0),   # Sensor 225° → Rail 270° mirror 0
            270: (180, 0),   # Sensor 270° → Rail 180° mirror 0
            315: (270, 1)    # Sensor 315° → Rail 270° mirror 1
        }
        
        try:
            angle_int = int(sensor_angle)
            if angle_int in sensor_config:
                return sensor_config[angle_int]  # Retorna (ângulo, mirror)
            else:
                print(f"Ângulo sensor {angle_int}° não mapeado, usando padrão (0°, mirror 0)")
                return (0, 0)
        except (ValueError, TypeError):
            print(f"Ângulo sensor inválido '{sensor_angle}', usando padrão (0°, mirror 0)")
            return (0, 0)

    def _get_rail_config_for_fma(self, fma_angle):
        """Obtém configuração completa de rail (ângulo, mirror) para FMA usando auto_rail_config"""
        # Configuração detalhada com mirrors para FMAs
        fma_config = {
            0: (0, 0),       # FMA 0° → Rail 0° mirror 0
            90: (180, 0),    # FMA 90° → Rail 180° mirror 0
            180: (0, 0),     # FMA 180° → Rail 0° mirror 0
            270: (180, 0),   # FMA 270° → Rail 180° mirror 0
        }
        
        try:
            angle_int = int(fma_angle)
            if angle_int in fma_config:
                return fma_config[angle_int]  # Retorna (ângulo, mirror)
            else:
                return (0, 0)
        except (ValueError, TypeError):
            return (0, 0)

class FDSFormGenerator:
    """Gerador de formulários para configuração FDS"""
    
    def __init__(self, root, fds_model='FDS101'):
        self.root = root
        self.fds_model = fds_model  # Armazena o modelo FDS selecionado
        self.root.title(f"Praxis - {fds_model} - Sistema de Configuração Ferroviária")
        self.root.geometry("1400x800")
        self.root.configure(bg='#f0f0f0')

        self._default_gateway_row = None
        self._default_gateway_pack_opts = None
        
        # Sistema de rastreamento de validação
        self.validation_state = {}  # {filename: {'validated': bool, 'errors': []}}
        self.last_validation_time = {}  # {filename: timestamp}
        self.content_hash = {}  # {filename: hash_string}
        self.changes_since_validation = False  # Flag geral de mudanças

        # Ícone da aplicação
        try:
            self.root.iconbitmap('favicon.ico')
        except:
            pass
        
        # Configurar estilo GEEE/MRS
        self.setup_corporate_style()
        
        self.current_generator = None
        self.form_fields = {}
        
        # Novos atributos para sistema integrado
        self.fds_config_data = {}  # Cache dos dados do FdsConfig.xml
        self.trackplan_data = {}   # Cache dos dados do Trackplan.xml
        
        # Sistema FMA
        self.fma_config_window = None
        self.current_fma_element = None
        self.highlighted_fma_elements = []  # Para teste visual
        
        # Sistema de gestão segura de imagens (correção PhotoImage)
        self.image_registry = {}  # Manter referências fortes às imagens
        
        # Aplicar patch preventivo para PhotoImage (Python 3.13)
        self.apply_photoimage_patch()
        
        self.create_widgets()

    def _sync_current_cubicle_from_editor(self):
        """Garante que current_cubicle reflita os valores do editor (inclui slots)."""
        try:
            if not getattr(self, 'current_cubicle', None):
                return
            rack = self.current_cubicle.setdefault('rack', {})
            bp = rack.setdefault('bp', {})
            # Copiar campos básicos do editor
            bp['id'] = self.bp_id_var.get()
            bp['size'] = self.bp_size_var.get()
            bp['startSlot'] = self.bp_start_slot_var.get()
            # Copiar slots do editor para o modelo
            bp['slots'] = copy.deepcopy(getattr(self, 'rack_slots', {}))
        except Exception as e:
            print(f"_sync_current_cubicle_from_editor: {e}")

    def create_safe_photo_image(self, pil_image, name_prefix="image"):
        """Cria PhotoImage de forma segura com correção para Python 3.13 e registry"""
        try:
            from PIL import ImageTk
            
            # Criar PhotoImage
            photo_image = ImageTk.PhotoImage(pil_image)
            
            # Correção preventiva para o bug do Python 3.13
            unique_name = f"{name_prefix}_{id(photo_image)}"
            if not hasattr(photo_image, 'name'):
                photo_image.name = unique_name
            
            # Manter referência forte no registry para prevenir garbage collection
            self.image_registry[unique_name] = photo_image
            
            return photo_image
        except Exception as e:
            print(f"Erro ao criar PhotoImage seguro: {e}")
            return None
    
    def clear_image_registry(self):
        """Limpa o registry de imagens para liberar memória"""
        self.image_registry.clear()
        
        # Limpar também as imagens de preview se existirem
        if hasattr(self, 'preview_images'):
            self.preview_images.clear()
    
    def _is_valid_ipv4(self, value: str) -> bool:
        """Valida IPv4 no formato 'a.b.c.d' com octetos 0..255."""
        try:
            ipaddress.IPv4Address((value or "").strip())
            return True
        except Exception:
            return False
    
    def apply_photoimage_patch(self):
        """Patch seguro para evitar crashes no __del__/name do PhotoImage"""
        try:
            from PIL import ImageTk
            # tk.Image pode não existir em alguns interpretes; proteger
            base = getattr(tk, "Image", None)
            if base:
                original_del = getattr(base, "__del__", None)
                def safe_del(self_img):
                    try:
                        if original_del:
                            original_del(self_img)
                    except Exception:
                        pass
                base.__del__ = safe_del

            original_init = ImageTk.PhotoImage.__init__
            def patched_init(self_img, image=None, size=None, **kw):
                original_init(self_img, image, size, **kw)
                if not hasattr(self_img, 'name') or not self_img.name:
                    self_img.name = f"PhotoImage_{id(self_img)}"
            ImageTk.PhotoImage.__init__ = patched_init
        except Exception as e:
            print(f"Erro ao aplicar patch PhotoImage: {e}")
    
    def setup_corporate_style(self):
        """Configura o estilo visual dos widgets"""
        style = ttk.Style()
        
        # Configurar tema base
        style.theme_use('winnative')
        
        # Paleta de cores
        colors = {
            'primary': '#073359',      # Azul escuro institucional MRS
            'secondary': '#093773',    # Azul médio institucional
            'accent': '#FFFF00',       # Amarelo institucional MRS
            'header_bg': '#1e3a5f',    # Azul escuro para header
            'header_text': '#FFFF00',  # Amarelo para títulos principais
            'subtitle': '#7bb3f0',     # Azul claro para subtítulos
            'success': '#28a745',      # Verde para sucesso
            'warning': '#ffc107',      # Amarelo para avisos
            'danger': '#dc3545',       # Vermelho para erros
            'light': '#f8f9fa',        # Cinza muito claro
            'dark': '#343a40',         # Cinza escuro
            'bg_gray': '#f0f0f0',      # Fundo cinza padrão
            'border': '#d0d0d0'        # Bordas suaves
        }
        
        try:
            # Botões principais
            style.configure('Corporate.TButton',
                           font=('Segoe UI', 9),
                           padding=(12, 6))
            
            style.configure('Primary.TButton',
                           font=('Segoe UI', 9, 'bold'),
                           padding=(15, 8))
            
            style.map('Primary.TButton',
                     background=[('active', colors['primary'])])
            
            # Botões de ação importantes
            style.configure('Success.TButton',
                           font=('Segoe UI', 10, 'bold'),
                           padding=(18, 10))
            
            style.map('Success.TButton',
                     background=[('active', colors['success'])])
            
            # Campos de entrada
            style.configure('Corporate.TEntry',
                           fieldbackground='white',
                           borderwidth=1,
                           relief='solid',
                           font=('Segoe UI', 9))
            
            # Labels corporativos
            style.configure('Corporate.TLabel',
                           font=('Segoe UI', 9),
                           background=colors['bg_gray'])
            
            style.configure('Title.TLabel',
                           font=('Segoe UI', 12, 'bold'),
                           background=colors['bg_gray'])
            
            # Frames de seção
            style.configure('Section.TLabelframe',
                           relief='solid',
                           borderwidth=1,
                           bordercolor=colors['border'],
                           background=colors['bg_gray'])
            
            style.configure('Section.TLabelframe.Label',
                           font=('Segoe UI', 11, 'bold'),
                           background=colors['bg_gray'],
                           foreground=colors['primary'])
            
            # Notebook corporativo
            style.configure('Corporate.TNotebook',
                           background=colors['bg_gray'],
                           borderwidth=0)
            
            style.configure('Corporate.TNotebook.Tab',
                           font=('Segoe UI', 10, 'bold'),
                           padding=(20, 12))
            
            # Frames transparentes
            style.configure('Transparent.TFrame',
                           background=colors['bg_gray'])
            
        except Exception as e:
            print(f"Aviso: Algumas configurações de estilo podem não estar disponíveis: {e}")

    def create_setup_bar(self):
        menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(menu_bar, tearoff=0)

        menu_abrir = tk.Menu(file_menu, tearoff=0)
        menu_abrir.add_command(label="FdsConfig.xml", command=self.load_fds_config)
        menu_abrir.add_command(label="Trackplan.xml", command=self.load_trackplan)
        menu_abrir.add_command(label="FdsRecovery.zip", command=self.load_fds_recovery)

        menu_salvar = tk.Menu(file_menu, tearoff=0)
        menu_salvar.add_command(label="FdsConfig.xml", command=self.save_fds_config)
        menu_salvar.add_command(label="Trackplan.xml", command=self.save_trackplan)
        menu_salvar.add_command(label="FdsRecovery.zip", command=self.save_all_files)

        file_menu.add_cascade(label="Abrir", menu=menu_abrir)
        file_menu.add_cascade(label="Salvar", menu=menu_salvar)

        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.root.quit)

        menu_bar.add_cascade(label="Arquivo", menu=file_menu)

        self.root.config(menu=menu_bar)

    def create_widgets(self):

        self.create_setup_bar()

        """Cria os widgets do formulário com design corporativo GEEE/MRS"""
        
        # === HEADER CORPORATIVO ===
        header_frame = tk.Frame(self.root, bg='#1e3a5f', height=110)  # Aumentado de 90 para 110
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        # Container para logo/título
        title_container = tk.Frame(header_frame, bg='#1e3a5f')
        title_container.pack(side=tk.LEFT, padx=25, pady=5)  # Aumentado padding vertical
        
        # Adicionar Logo GEEE
        try:
            # Carregar logo
            logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
            if os.path.exists(logo_path):
                from PIL import Image, ImageTk
                # Redimensionar logo para caber no header (ajuste o tamanho conforme necessário)
                logo_image = Image.open(logo_path)
                logo_image = logo_image.resize((80, 80), Image.Resampling.LANCZOS)  # Ajuste o tamanho
                self.logo_photo = ImageTk.PhotoImage(logo_image)
                
                # Container para logo e texto
                logo_text_frame = tk.Frame(title_container, bg='#1e3a5f')
                logo_text_frame.pack(anchor="w")
                
                # Logo à esquerda
                logo_label = tk.Label(logo_text_frame, image=self.logo_photo, bg='#1e3a5f')
                logo_label.pack(side=tk.LEFT, padx=(0, 15))
                
                # Texto à direita do logo
                text_frame = tk.Frame(logo_text_frame, bg='#1e3a5f')
                text_frame.pack(side=tk.LEFT)
                
                # Título principal (sem GEEE)
                self.title_label = tk.Label(text_frame, 
                                      text=f"Praxis - {self.fds_model}", 
                                      font=('Segoe UI', 18, 'bold'),
                                      fg='#FFFF00', 
                                      bg='#1e3a5f')
                self.title_label.pack(anchor="w")
                
                # Subtítulo
                subtitle_label = tk.Label(text_frame, 
                                         text="Sistema de Configuração Ferroviária para o FDS", 
                                         font=('Segoe UI', 11),
                                         fg='#7bb3f0', 
                                         bg='#1e3a5f')
                subtitle_label.pack(anchor="w", pady=(2, 0))
                
            else:
                # Fallback se não encontrar a imagem
                print(f"Logo não encontrado em: {logo_path}")
                self._create_text_only_header(title_container)
                
        except ImportError:
            # Fallback se PIL não estiver disponível
            print("PIL não disponível - usando header apenas texto")
            self._create_text_only_header(title_container)
        except Exception as e:
            # Fallback para qualquer outro erro
            print(f"Erro ao carregar logo: {e}")
            self._create_text_only_header(title_container)
        
        # Container para informações da empresa (lado direito)
        company_container = tk.Frame(header_frame, bg='#1e3a5f')
        company_container.pack(side=tk.RIGHT, padx=25, pady=5)
        
        # Logo/texto MRS
        mrs_label = tk.Label(company_container, 
                            text="MRS   ", 
                            font=('Segoe UI', 16),
                            fg='#FFFF00', 
                            bg='#1e3a5f')
        mrs_label.pack(anchor="e")
        
        # Subtítulo MRS
        mrs_subtitle = tk.Label(company_container, 
                               text="Logística S.A.", 
                               font=('Segoe UI', 10),
                               fg='#7bb3f0', 
                               bg='#1e3a5f')
        mrs_subtitle.pack(anchor="e")
        
        # === RODAPÉ ===
        footer_frame = tk.Frame(self.root, bg='#1e3a5f', height=35)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X)
        footer_frame.pack_propagate(False)
        
        # Container principal do rodapé
        footer_content = tk.Frame(footer_frame, bg='#1e3a5f')
        footer_content.pack(fill=tk.BOTH, expand=True)
        
        # Configurar o grid do frame para expansão
        footer_content.grid_columnconfigure(0, weight=1)
        footer_content.grid_columnconfigure(1, weight=2) 
        footer_content.grid_columnconfigure(2, weight=1)
        footer_content.grid_rowconfigure(0, weight=1)

        # Texto do rodapé 
        footer_label = tk.Label(footer_content, 
                            text="GEEE - Gerência de Engenharia de Eletroeletrônica | MRS Logística © 2026", 
                            font=('Segoe UI', 8),
                            fg='#7bb3f0', 
                            bg='#1e3a5f')
        footer_label.grid(row=0, column=1, padx=5, pady=5, sticky="")
        
        # Botão de ajuda (lado direito)
        help_button = tk.Button(footer_content,
                            text="❓",
                            font=('Segoe UI', 12, 'bold'),
                            bg='#0078d4',
                            fg='white',
                            relief='raised',
                            borderwidth=2,
                            width=3,
                            height=1,
                            command=self.show_help_window,
                            cursor='hand2')
        help_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        
        # Tooltip para o botão de ajuda
        self._create_tooltip(help_button, "Clique para acessar a ajuda do sistema")
        
        # === CONTAINER PRINCIPAL PARA NOTEBOOK ===
        main_container = tk.Frame(self.root, bg='#f0f0f0')
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # === Notebook ===
        self.notebook = ttk.Notebook(main_container, style='Corporate.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Aba 1: Configuração FDS
        self.create_fds_config_tab()
        
        # Aba 2: Designer de Trackplan
        self.create_trackplan_designer_tab()
        
        # Aba 3: Programação de Cubicles
        self.create_cubicles_tab()
        
        #Aba 4: Configuração
        self.create_config_tab()

        # Aba 5: Visualização XML
        self.create_xml_preview_tab()

    def show_help_window(self):
        """Mostra a janela de ajuda como uma janela separada"""
        # Verificar se a janela já existe
        if hasattr(self, 'help_window') and self.help_window and self.help_window.winfo_exists():
            # Se já existe, apenas trazer para frente
            self.help_window.lift()
            self.help_window.focus_force()
            return
        
        # Criar nova janela de ajuda
        self.help_window = tk.Toplevel(self.root)
        self.help_window.title("Ajuda - Praxis")
        self.help_window.geometry("1200x800")
        self.help_window.transient(self.root)
        
        # Ícone da janela (se disponível)
        try:
            self.help_window.iconbitmap('favicon.ico')
        except:
            pass
        
        # Centralizar janela
        self.help_window.update_idletasks()
        x = (self.help_window.winfo_screenwidth() // 2) - 600
        y = (self.help_window.winfo_screenheight() // 2) - 400
        self.help_window.geometry(f"1200x800+{x}+{y}")
        
        # === LAYOUT PRINCIPAL DA JANELA DE AJUDA ===
        main_paned = ttk.PanedWindow(self.help_window, orient='horizontal')
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # === PAINEL ESQUERDO: LISTA DE TÓPICOS ===
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        # Cabeçalho da lista
        list_header = ttk.Frame(left_frame)
        list_header.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        ttk.Label(list_header, text="Tópicos de Ajuda", font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
        
        # Campo de busca
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(search_frame, text="🔍", font=('Arial', 10)).pack(side=tk.LEFT)
        self.help_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.help_search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # Implementar placeholder manualmente
        self._setup_search_placeholder(search_entry, "Buscar na ajuda...")
        
        # Não adicionar trace aqui - será adicionado em _setup_search_placeholder
        
        # TreeView para tópicos hierárquicos
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.help_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.help_tree.yview)
        self.help_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.help_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # === PAINEL DIREITO: CONTEÚDO DA AJUDA ===
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        
        # Cabeçalho do conteúdo
        content_header = ttk.Frame(right_frame)
        content_header.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        self.help_title_var = tk.StringVar(value="Bem-vindo ao Praxis")
        title_label = ttk.Label(content_header, textvariable=self.help_title_var, 
                            font=('Arial', 16, 'bold'), foreground="#0078d4")
        title_label.pack(anchor="w")
        
        # Breadcrumb
        self.help_breadcrumb_var = tk.StringVar(value="Início")
        breadcrumb_label = ttk.Label(content_header, textvariable=self.help_breadcrumb_var, 
                                font=('Arial', 9), foreground="gray")
        breadcrumb_label.pack(anchor="w", pady=(2, 0))
        
        # Separador
        separator = ttk.Separator(right_frame, orient='horizontal')
        separator.pack(fill=tk.X, padx=10, pady=10)
        
        # Área de conteúdo scrollável
        content_canvas = tk.Canvas(right_frame, bg="#f0f0f0", highlightthickness=0)
        content_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=content_canvas.yview)
        self.help_content_frame = ttk.Frame(content_canvas)
        
        self.help_content_frame.bind(
            "<Configure>",
            lambda e: content_canvas.configure(scrollregion=content_canvas.bbox("all"))
        )
        
        content_canvas.create_window((0, 0), window=self.help_content_frame, anchor="nw")
        content_canvas.configure(yscrollcommand=content_scrollbar.set)
        
        content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))
        
        # Bind para seleção de tópicos
        self.help_tree.bind("<<TreeviewSelect>>", self.on_help_topic_select)
        
        # Bind para scroll com mouse wheel
        def _on_mousewheel(event):
            content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        content_canvas.bind("<MouseWheel>", _on_mousewheel)
        
        # Configurar proporção dos painéis
        self.help_window.after(100, lambda: self._set_paned_position(main_paned))
        
        # Botão de fechar na parte inferior
        footer_help = ttk.Frame(self.help_window)
        footer_help.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(footer_help, text="Fechar Ajuda", 
                command=self.help_window.destroy).pack(side=tk.RIGHT)
        
        # Carregar estrutura de ajuda
        self.load_help_structure()
        self.show_help_welcome()
        
        # Focar na janela
        self.help_window.focus_force()

    def _create_tooltip(self, widget, text):
        """Cria tooltip para um widget"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = tk.Label(tooltip, text=text, 
                            background='#ffffe0', 
                            relief='solid', 
                            borderwidth=1,
                            font=('Segoe UI', 8))
            label.pack()
            
            # Armazenar referência do tooltip no widget
            widget.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
        
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def _create_text_only_header(self, title_container):
        """Cria header apenas com texto (fallback)"""
        # Título principal (sem GEEE)

        title_label = tk.Label(title_container, 
                              text=f"Praxis - {self.fds_model}", 
                              font=('Segoe UI', 18, 'bold'),
                              fg='#FFFF00', 
                              bg='#1e3a5f')
        title_label.pack(anchor="w")
        
        # Subtítulo
        subtitle_label = tk.Label(title_container, 
                                 text="Sistema de Configuração Ferroviária", 
                                 font=('Segoe UI', 11),
                                 fg='#7bb3f0', 
                                 bg='#1e3a5f')
        subtitle_label.pack(anchor="w", pady=(2, 0))

    def _set_default_gateway_visibility(self, visible: bool):
        """Mostra/oculta o campo DefaultGateway (FDS102) sem recriar a aba."""
        try:
            row = getattr(self, "_default_gateway_row", None)
            if row is None:
                return

            if visible:
                # re-pack com as mesmas opções usadas na criação
                opts = self._default_gateway_pack_opts or {"fill": tk.X, "pady": (0, 15)}
                # evitar erro se já estiver visível
                try:
                    row.pack(**opts)
                except Exception:
                    pass
            else:
                try:
                    row.pack_forget()
                except Exception:
                    pass
        except Exception as e:
            print(f"_set_default_gateway_visibility: {e}")

    def apply_fds_model(self, new_model: str, remember: bool = False):
        """Troca o modo FDS (101/102) e atualiza UI dinâmica (sem reiniciar)."""
        if new_model not in ("FDS101", "FDS102"):
            return

        self.fds_model = new_model
        try:
            self.root.title(f"Praxis - {new_model} - Sistema de Configuração Ferroviária")
            self.title_label.config(text=f"Praxis - {new_model}")
        except Exception:
            pass

        # Toggle imediato do campo do FDS102
        self._set_default_gateway_visibility(new_model == "FDS102")

        if self.fds_model == "FDS102":
            self.form_fields["TimeZone"].set("America/Sao_Paulo")
        else:
            self.form_fields["TimeZone"].set("CET-1CEST-2,M3.5.0/02:00:00,M10.5.0/03:00:00")

        # Persistência (se você quiser manter)
        try:
            save_user_config(new_model, bool(remember))
        except Exception as e:
            print(f"apply_fds_model: falha ao salvar config: {e}")

    def create_fds_config_tab(self):
        """Cria a aba de configuração FDS com design corporativo"""
        frame = ttk.Frame(self.notebook, style='Transparent.TFrame')
        self.notebook.add(frame, text="Configuração FDS")
        
        # Scrollable frame com canvas limpo
        canvas = tk.Canvas(frame, bg='#f0f0f0', highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Transparent.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # === SEÇÃO: CONFIGURAÇÕES BÁSICAS ===
        basic_frame = ttk.LabelFrame(scrollable_frame, text="Configurações Básicas", 
                                    padding=20, style='Section.TLabelframe')
        basic_frame.pack(fill=tk.X, padx=20, pady=(15, 10))
        
        # Criar grid organizado para campos básicos
        basic_grid = ttk.Frame(basic_frame, style='Transparent.TFrame')
        basic_grid.pack(fill=tk.X)
        
        # Primeira linha de campos
        row1 = ttk.Frame(basic_grid, style='Transparent.TFrame')
        row1.pack(fill=tk.X, pady=(0, 15))
        
        self.create_form_field_styled(row1, "ConfigVersion", "1.0", "Versão da Configuração:", True, False)
        self.create_form_field_styled(row1, "StationName", "", "Nome da Estação:", False, False)
        
        # Segunda linha de campos
        row2 = ttk.Frame(basic_grid, style='Transparent.TFrame')
        row2.pack(fill=tk.X, pady=(0, 15))

        self.create_form_field_styled(row2, "FdsName", "", "Nome do FDS:", True, False)

        if self.fds_model == "FDS102":
            self.create_form_field_styled(row2, "TimeZone", "America/Sao_Paulo", "Timezone:", False, True)
        else:
            self.create_form_field_styled(row2, "TimeZone", "CET-1CEST-2,M3.5.0/02:00:00,M10.5.0/03:00:00", "Timezone:", False, True)
        
        # === SEÇÃO: CONFIGURAÇÕES DE REDE ===
        network_frame = ttk.LabelFrame(scrollable_frame, text="Configurações de Rede", 
                                      padding=20, style='Section.TLabelframe')
        network_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Grid para configurações de rede
        network_grid = ttk.Frame(network_frame, style='Transparent.TFrame')
        network_grid.pack(fill=tk.X)
        
        # Linha dedicada para seleção da rede do Trackplan
        net_select_row = ttk.Frame(network_grid, style='Transparent.TFrame')
        net_select_row.pack(fill=tk.X, pady=(0, 10))

        net_select_box = ttk.LabelFrame(
            net_select_row,
            text="Rede atual para uso",
            padding=8,
            style='Section.TLabelframe'
        )
        net_select_box.pack(fill=tk.X)

        self.selected_rede = tk.StringVar(value="IP Rede1")
        self.form_fields["TrackplanNetwork"] = self.selected_rede

        ttk.Radiobutton(
            net_select_box,
            text="IP Rede 1",
            variable=self.selected_rede,
            value="IP Rede1"
        ).pack(side=tk.LEFT, padx=(8, 20))

        ttk.Radiobutton(
            net_select_box,
            text="IP Rede 2",
            variable=self.selected_rede,
            value="IP Rede2"
        ).pack(side=tk.RIGHT, padx=(8, 20))

        # Primeira linha - IPs
        net_row1 = ttk.Frame(network_grid, style='Transparent.TFrame')
        net_row1.pack(fill=tk.X, pady=(0, 15))
        
        # Segunda linha - IPs
        net_row2 = ttk.Frame(network_grid, style='Transparent.TFrame')
        net_row2.pack(fill=tk.X, pady=(0, 15))

        self.create_form_field_styled(net_row1, "IpAddressNet1", "192.168.1.12", "IP Rede 1:", True, False)
        self.create_form_field_styled(net_row1, "IpAddressNet2", "192.168.0.12", "IP Rede 2:", False, False)

        self.create_form_field_styled(net_row2, "MaskNet1", "255.255.255.0", "Máscara Rede 1:", True, False)
        self.create_form_field_styled(net_row2, "MaskNet2", "255.255.255.0", "Máscara Rede 2:", False, False)

        # Terceira linha - Gateways
        net_row3 = ttk.Frame(network_grid, style='Transparent.TFrame')
        net_row3.pack(fill=tk.X, pady=(0, 15))

        self.create_form_field_styled(net_row3, "GatewayAddressNet1", "192.168.1.1", "Gateway Rede 1:", True, False)
        self.create_form_field_styled(net_row3, "GatewayAddressNet2", "192.168.0.1", "Gateway Rede 2:", False, False)

        # Quarta linha - Portas e Servidores
        net_row4 = ttk.Frame(network_grid, style='Transparent.TFrame')
        net_row4.pack(fill=tk.X, pady=(0, 15))

        self.create_form_field_styled(net_row4, "TimeServer1", "192.168.103.172", "Servidor Tempo 1:", True, False)
        self.create_form_field_styled(net_row4, "TimeServer2", "192.168.103.173", "Servidor Tempo 2:", True, False)
        self.create_form_field_styled(net_row4, "UdpPortFadc", "45", "Porta UDP FADC:", False, True)
        
        # Quinta linha - Default Gateway (somente para FDS102)
        self._default_gateway_row = ttk.Frame(network_grid, style='Transparent.TFrame')
        self._default_gateway_row.pack(fill=tk.X, pady=(0, 15))

        gateway_container = ttk.Frame(self._default_gateway_row, style='Transparent.TFrame')
        gateway_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15))

        label = ttk.Label(gateway_container, text="Default Gateway", 
                        font=('Segoe UI', 9, 'bold'), style='Corporate.TLabel')
        label.pack(anchor=tk.W, pady=(0, 5))

        def defocus(event):
            event.widget.master.focus_set()

        var = tk.StringVar(value="Gateway2")
        DefaultGateway = ttk.Combobox(gateway_container,
                                    values=["Gateway1", "Gateway2"], textvariable=var, 
                                    font=('Segoe UI', 9), state='readonly')
        DefaultGateway.pack(fill=tk.X, ipady=3)
        DefaultGateway.bind("<FocusIn>", defocus)

        self.form_fields["DefaultGateway"] = var

        if self.fds_model != "FDS102":
            self._default_gateway_row.pack_forget()

        # === SEÇÃO: ELEMENTOS ===
        elements_frame = ttk.LabelFrame(scrollable_frame, text="Elementos do Sistema", 
                                       padding=20, style='Section.TLabelframe')
        elements_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Botões para elementos com estilo corporativo
        elements_buttons = ttk.Frame(elements_frame, style='Transparent.TFrame')
        elements_buttons.pack(fill=tk.X, pady=(0, 15))
        
        # Primeira linha de botões
        btn_row1 = ttk.Frame(elements_buttons, style='Transparent.TFrame')
        btn_row1.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Button(btn_row1, text="➕ ComMaster", command=self.add_com_master, 
                  style='Corporate.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_row1, text="➕ AEB", command=self.add_aeb, 
                  style='Corporate.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_row1, text="➕ CountingHead", command=self.add_counting_head, 
                  style='Corporate.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_row1, text="➕ TrackSection", command=self.add_track_section, 
                  style='Corporate.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_row1, text="➖ Remover Elementos", command=self.remove_elements, 
                  style='Corporate.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_row1, text="🧹 Limpar Todos", command=self.clear_all_elements, 
                  style='Corporate.TButton').pack(side=tk.LEFT, padx=(0, 10))
        
        # === BARRA DE PESQUISA ===
        search_frame = ttk.Frame(elements_frame, style='Transparent.TFrame')
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="Pesquisar por Element ID/Tipo/Atribuição:", 
                 font=('Segoe UI', 9, 'bold'), style='Corporate.TLabel').pack(side=tk.LEFT, padx=(0, 10))
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', self.filter_elements_tree)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, 
                               style='Corporate.TEntry', font=('Segoe UI', 9), width=20)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(search_frame, text="Limpar", command=self.clear_search).pack(side=tk.LEFT)

        # Lista de elementos com headers melhorados
        tree_frame = ttk.Frame(elements_frame, style='Transparent.TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.elements_tree = ttk.Treeview(tree_frame, columns=("ID", "Tipo", "Atribuição", "TrackplanID"), 
                                         show="headings", height=10)
        self.elements_tree.heading("ID", text="Element ID")
        self.elements_tree.heading("Tipo", text="Tipo")
        self.elements_tree.heading("Atribuição", text="Atribuição")
        self.elements_tree.heading("TrackplanID", text="ID")
        
        # Ajustar larguras das colunas
        self.elements_tree.column("ID", width=100, anchor="center")
        self.elements_tree.column("Tipo", width=120, anchor="w")
        self.elements_tree.column("Atribuição", width=200, anchor="w")
        self.elements_tree.column("TrackplanID", width=120, anchor="center")
        
        elements_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.elements_tree.yview)
        self.elements_tree.configure(yscrollcommand=elements_scrollbar.set)
        
        self.elements_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        elements_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # === SEÇÃO: AÇÕES PRINCIPAIS ===
        actions_frame = ttk.Frame(scrollable_frame, style='Transparent.TFrame')
        actions_frame.pack(fill=tk.X, padx=20, pady=(15, 20))
        
        # Separador visual
        separator = ttk.Separator(actions_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=(0, 15))
        
        # Container centralizado para botões principais
        buttons_container = ttk.Frame(actions_frame, style='Transparent.TFrame')
        buttons_container.pack(anchor=tk.CENTER)
        
        # Botões principais organizados
        main_buttons = ttk.Frame(buttons_container, style='Transparent.TFrame')
        main_buttons.pack()
        
        # Primeira linha de botões principais
        btn_main_row1 = ttk.Frame(main_buttons, style='Transparent.TFrame')
        btn_main_row1.pack(pady=(0, 10))
        
        ttk.Button(btn_main_row1, text="Carregar FdsConfig.xml", command=self.load_fds_config, 
                  style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Button(btn_main_row1, text="Salvar FdsConfig.xml", command=self.save_config, 
                  style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Button(btn_main_row1, text="Importar dos Cubículos", command=self.import_from_cubicles,
                  style='Primary.TButton').pack(side=tk.LEFT, padx=(0, 15))
        
        # Pack do canvas e scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configurar scroll com mouse wheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_to_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind('<Enter>', _bind_to_mousewheel)
        canvas.bind('<Leave>', _unbind_from_mousewheel)
        
        # Inicializar gerador
        self.initialize_generator()
        

    def load_fds_config(self, filename=None):
        """Carrega um FdsConfig.xml e preenche os campos do formulário"""
        if filename is None:
            filename = filedialog.askopenfilename(
                title="Carregar FdsConfig.xml",
                defaultextension=".xml",
                filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
            )

        if not filename:
            return

        try:
            # String de caminho
            if isinstance(filename, str):
                tree = ET.parse(filename)

            # Bytes (conteúdo vindo do zip)
            elif isinstance(filename, bytes):
                tree = ET.ElementTree(ET.fromstring(filename))

            # File-like object
            else:
                tree = ET.parse(filename)

            root = tree.getroot()

            # Armazenar o XML carregado
            self.fds_config_data = {'root': root, 'filename': filename}
            # Preencher campos básicos
            self.form_fields["ConfigVersion"].set(root.findtext("ConfigVersion", default="1.0"))
            self.form_fields["StationName"].set(root.findtext("StationName", default="AREAIS"))
            self.form_fields["FdsName"].set(root.findtext("FdsName", default="AREAIS"))
            if self.fds_model == "FDS102":
                self.form_fields["DefaultGateway"].set(root.findtext("DefaultGateway", default="Gateway2"))
                self.form_fields["TimeZone"].set("America/Sao_Paulo")
            else:
                self.form_fields["TimeZone"].set("CET-1CEST-2,M3.5.0/02:00:00,M10.5.0/03:00:00")
            # Preencher campos de rede
            self.form_fields["IpAddressNet1"].set(root.findtext("IpAddressNet1", default="192.168.1.27"))
            self.form_fields["MaskNet1"].set(root.findtext("MaskNet1", default="255.255.255.0"))
            self.form_fields["IpAddressNet2"].set(root.findtext("IpAddressNet2", default="192.168.0.12"))
            self.form_fields["MaskNet2"].set(root.findtext("MaskNet2", default="255.255.255.0"))
            self.form_fields["GatewayAddressNet1"].set(root.findtext("GatewayAddressNet1", default="192.168.1.27"))
            self.form_fields["GatewayAddressNet2"].set(root.findtext("GatewayAddressNet2", default="192.168.0.1"))
            self.form_fields["UdpPortFadc"].set(root.findtext("UdpPortFadc", default="45"))
            self.form_fields["TimeServer1"].set(root.findtext("TimeServer1", default="192.168.103.172"))
            self.form_fields["TimeServer2"].set(root.findtext("TimeServer2", default="192.168.103.173"))
            
            # Inicializar gerador primeiro
            self.initialize_generator()
            
            # Carregar elementos existentes do XML
            self.load_elements_from_xml(root)
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar FdsConfig.xml: {str(e)}")
    
    def load_elements_from_xml(self, root):
        """Carrega elementos (ComMaster, Aeb, CountingHead, TrackSection1/2) do XML no formato com nós filhos.

        Espera a estrutura:
          <Element>
            <ElementId>...</ElementId>
            <ElementType>ComMaster|Aeb|CountingHead|TrackSection1|TrackSection2</ElementType>
            <ElementAssignment>...</ElementAssignment>
            <ElementTrackplanId>...</ElementTrackplanId>  (opcional ao carregar)
          </Element>
        """
        try:
            # Verificar se o gerador está disponível
            if not hasattr(self, 'current_generator') or not self.current_generator:
                print("ERRO: current_generator não está disponível")
                messagebox.showerror("Erro", "Gerador não inicializado. Tente carregar novamente.")
                return

            # Verificar disponibilidade de ElementConfig
            if ElementConfig is None:
                print("ERRO: ElementConfig indisponível (módulo fds_config_generator não carregado)")
                messagebox.showerror(
                    "Erro",
                    "Biblioteca fds_config_generator não encontrada. Verifique se o arquivo fds_config_generator.py está presente."
                )
                return

            # Limpar elementos existentes
            self.current_generator.elements.clear()
            elements_loaded = 0
            errors = []

            # Procurar por ElementList
            element_list = root.find("ElementList")
            if element_list is None:
                print("ERRO: ElementList não encontrada no XML")
                messagebox.showerror("Erro", "Estrutura XML inválida: ElementList não encontrada")
                return

            # Buscar todos os elementos
            elements = element_list.findall("Element")

            if len(elements) == 0:
                print("Nenhum elemento encontrado")
                messagebox.showwarning("Aviso", "Nenhum elemento encontrado no XML")
                return

            def normalize_type(raw_type: str) -> str:
                if not raw_type:
                    return ""
                t = raw_type.strip()
                tl = t.lower()
                if tl == "commaster":
                    return "ComMaster"
                if tl == "aeb":
                    return "Aeb"
                if tl == "countinghead":
                    return "CountingHead"
                if tl == "ioexb":
                    return "Ioexb"
                if tl in ("fma1", "tracksection1"):
                    return "TrackSection1"
                if tl in ("fma2", "tracksection2"):
                    return "TrackSection2"
                return t  # fallback original

            # Processar cada elemento
            for i, element in enumerate(elements):
                try:
                    element_id_raw = element.findtext("ElementId", "").strip()
                    element_type_raw = element.findtext("ElementType", "").strip()
                    element_assignment_raw = element.findtext("ElementAssignment", "").strip()
                    
                    if element_type_raw in ['ForwardingMaster', 'TrackSectionExtern1','TrackSectionExtern2']:
                        continue

                    if not element_id_raw or not element_type_raw:
                        error_msg = f"Elemento {i+1}: ID ou Type vazio - Ignorando"
                        print(error_msg)
                        errors.append(error_msg)
                        continue

                    element_type = normalize_type(element_type_raw)
                    try:
                        element_id = int(element_id_raw)
                    except ValueError:
                        error_msg = f"Elemento {i+1}: ID '{element_id_raw}' inválido - Ignorando"
                        print(error_msg)
                        errors.append(error_msg)
                        continue

                    if element_type == "ComMaster":
                        # Se a atribuição não tem o ID, adicionar
                        normalized_id = self._normalize_element_id(element_id)
                        expected_assignment = f"COM{normalized_id}"
                        
                        if element_assignment_raw != expected_assignment:
                            element_assignment = expected_assignment
                        else:
                            element_assignment = element_assignment_raw
                    else:
                        element_assignment = element_assignment_raw

                    element_config = ElementConfig(element_id, element_type, element_assignment)
                    self.current_generator.add_element(element_config)
                    elements_loaded += 1
                    
                except Exception as e:
                    error_msg = f"Erro ao processar elemento {i+1}: {e}"
                    print(error_msg)
                    errors.append(error_msg)
                    continue

            # Atualizar árvore de elementos
            self.update_elements_tree()

            # Mostrar resultado para o usuário
            if elements_loaded > 0:
                if errors:
                    messagebox.showinfo(
                        "Carregamento Parcial",
                        f"Carregados {elements_loaded} elementos com {len(errors)} erros.\n\nVerifique o console para detalhes."
                    )
                else:
                    messagebox.showinfo("Sucesso", f"Todos os {elements_loaded} elementos foram carregados com sucesso!")
            else:
                if errors:
                    messagebox.showerror(
                        "Erro",
                        f"Nenhum elemento pôde ser carregado. {len(errors)} erros encontrados.\n\nVerifique o console para detalhes."
                    )
                else:
                    messagebox.showwarning("Aviso", "Nenhum elemento foi encontrado no arquivo XML.")

        except Exception as e:
            error_msg = f"Erro geral ao carregar elementos do XML: {e}"
            print(error_msg)
            messagebox.showerror("Erro Crítico", error_msg)
    
    def update_trackplan_fds_name(self):
        """Atualiza o nome do FDS mostrado acima do canvas baseado no Trackplan.xml carregado"""
        try:
            fds_name = None
            
            # Buscar no Trackplan.xml carregado
            if hasattr(self, 'trackplan_data') and self.trackplan_data:
                try:
                    # Verificar se temos dados do XML carregado
                    if 'root' in self.trackplan_data:
                        root = self.trackplan_data['root']
                        
                        # Buscar elemento Fds no XML
                        fds_elem = root.find("Fds")
                        if fds_elem is not None:
                            fds_name = fds_elem.get('name')
                            if not fds_name:
                                print("Elemento Fds encontrado mas sem atributo 'name'")
                        else:
                            print("Elemento Fds não encontrado no Trackplan.xml")
                    else:
                        print("trackplan_data não contém 'root'")
                        
                except Exception as e:
                    print(f"Erro ao extrair nome do Trackplan.xml: {e}")
            
            # Fallback para o formulário FdsConfig se não encontrou no Trackplan
            if not fds_name:
                try:
                    form_name = self.form_fields.get("FdsName", tk.StringVar()).get().strip()
                    if form_name:
                        fds_name = form_name
                except Exception as e:
                    print(f"⚠️ Erro ao obter nome do formulário: {e}")
            
            # Nome padrão se nada foi encontrado
            if not fds_name:
                fds_name = "Trackplan - Carregue um Trackplan.xml ou configure um nome na aba de Configuração FDS"
            
            # Atualizar o texto no label
            self.trackplan_fds_name_var.set(fds_name)

        except Exception as e:
            print(f"Erro ao atualizar nome do FDS: {e}")
            # Em caso de erro, usar mensagem de erro clara
            try:
                self.trackplan_fds_name_var.set("Trackplan - Erro ao carregar nome")
            except:
                pass

    def _base_id_from_prefixed_or_can(self, slot: dict, kind: str):
        """Extrai o 'base id' (int) a partir do slot.
        Prioridade:
          1) canId (quando existir e for numérico)
          2) id (removendo prefixo típico do tipo, se fizer sentido)
        Retorna None se não conseguir.
        """
        try:
            # 1) canId (melhor fonte para COM/AEB)
            can_id = str(slot.get("canId", "")).strip()
            if can_id.isdigit():
                return int(can_id)

            # 2) fallback: slot["id"]
            raw = str(slot.get("id", "")).strip()
            digits = "".join(ch for ch in raw if ch.isdigit())
            if not digits:
                return None

            # Se o ID vier com prefixo (0xxxx para COM, 1xxxx para AEB),
            # usar o sufixo como base.
            if kind == "Com" and digits.startswith("0") and len(digits) > 1:
                tail = digits[1:]
                return int(tail) if tail.isdigit() else int(digits)

            if kind == "Aeb" and digits.startswith("1") and len(digits) > 1:
                tail = digits[1:]
                return int(tail) if tail.isdigit() else int(digits)

            return int(digits)
        except Exception:
            return None

    def import_from_cubicles(self):
        """ Importa itens dos cubículos para a lista de elementos do FdsConfig.xml"""
        try:
            # Pré-requisitos
            if not getattr(self, "current_generator", None):
                messagebox.showwarning("Aviso", "Gerador FDS não inicializado. Tente recarregar a aba ou abrir um FdsConfig.xml.")
                return

            if ElementConfig is None:
                messagebox.showerror("Erro", "ElementConfig indisponível (fds_config_generator não carregado).")
                return

            cubs = getattr(self, "cubicles_data", None) or []
            if not cubs:
                messagebox.showinfo("Importar dos Cubículos", "Não há cubículos para importar.")
                return

            # Perguntar estratégia
            clear_first = messagebox.askyesno(
                "Importar dos Cubículos",
                "Deseja LIMPAR a lista atual de elementos do FdsConfig antes de importar?\n\n"
                "Sim = substituir\nNão = mesclar (evita duplicados)"
            )
            if clear_first:
                try:
                    self.current_generator.elements.clear()
                except Exception:
                    self.current_generator.elements = []

            imported_com = 0
            imported_aeb = 0
            skipped = 0
            errors = 0

            # Coletar
            for cub in cubs:
                slots = (cub.get("rack", {}) or {}).get("bp", {}).get("slots", {}) or {}
                for _slotno, slot in slots.items():
                    stype = (slot.get("type") or "").strip()

                    if stype not in ("Com", "Aeb"):
                        continue

                    base_id = self._base_id_from_prefixed_or_can(slot, stype)
                    if base_id is None:
                        errors += 1
                        continue

                    # Construir elemento
                    if stype == "Com":
                        if not self.verifica_unico(base_id, "ComMaster"):
                            skipped += 1
                            continue
                        assignment = slot.get("name") or f"COM{base_id:04d}"
                        try:
                            # Preferir método do gerador, se existir
                            if hasattr(self.current_generator, "add_com_master"):
                                self.current_generator.add_com_master(base_id)
                            else:
                                self.current_generator.add_element(ElementConfig(base_id, "ComMaster", assignment))
                            imported_com += 1
                        except Exception:
                            errors += 1

                    elif stype == "Aeb":
                        if not self.verifica_unico(base_id, "Aeb"):
                            skipped += 1
                            continue
                        try:
                            # Evitar add_aeb_with_counting_head (pode criar CountingHead sem querer).
                            self.current_generator.add_aeb_with_counting_head(base_id)
                            imported_aeb += 1
                        except Exception:
                            errors += 1

            # Atualizar UI
            self.update_elements_tree()
            self._mark_content_changed()

            messagebox.showinfo(
                "Importar dos Cubículos",
                f"Importação concluída.\n\n"
                f"COM importadas: {imported_com}\n"
                f"AEB importadas: {imported_aeb}\n"
                f"ZPs importados: {imported_aeb}\n"
                f"Ignoradas (duplicadas): {skipped}\n"
                f"Com erro: {errors}"
            )

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao importar dos cubículos: {e}")

    def create_form_field(self, parent, label, default_value, row):
        """Cria um campo de formulário"""
        ttk.Label(parent, text=f"{label}:").grid(row=row, column=0, sticky=tk.W, pady=2)
        
        var = tk.StringVar(value=default_value)
        entry = ttk.Entry(parent, textvariable=var, width=40)
        entry.grid(row=row, column=1, sticky=tk.W, pady=2, padx=5)
        
        self.form_fields[label] = var
        
        return var, entry
    
    def create_form_field_styled(self, parent, field_name, default_value, label_text, is_left_column, readonly):
        """Cria um campo de formulário com estilo corporativo em layout de duas colunas"""
        # Container para o campo
        field_container = ttk.Frame(parent, style='Transparent.TFrame')
        
        if is_left_column:
            field_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 15))
        else:
            field_container.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Label com estilo corporativo
        label = ttk.Label(field_container, text=label_text, 
                        font=('Segoe UI', 9, 'bold'), style='Corporate.TLabel')
        label.pack(anchor=tk.W, pady=(0, 5))
        
        # Campo de entrada
        if readonly:
            var = tk.StringVar(value=default_value)
            entry = ttk.Entry(field_container, textvariable=var, 
                            style='Corporate.TEntry', font=('Segoe UI', 9), state='readonly')
            entry.pack(fill=tk.X, ipady=3)
        else:
            var = tk.StringVar(value=default_value)
            entry = ttk.Entry(field_container, textvariable=var, 
                            style='Corporate.TEntry', font=('Segoe UI', 9))
            entry.pack(fill=tk.X, ipady=3)
            
            # *** NOVO: Adicionar trace para atualizar nome do FDS ***
            if field_name == "FdsName":
                var.trace_add('write', lambda *args: self.update_trackplan_fds_name())

        # Armazenar referência
        self.form_fields[field_name] = var
        
        return var, entry
    
    def fix_grid(self):
        """ Ajusta a grid ao desenho"""
        maiorx = 0
        maiory = 0

        for element in self.trackplan_elements:
            x = element.get("x")
            y = element.get("y")
            if x is not None and y is not None:
                if x > maiorx:
                    maiorx = x
                if y > maiory:
                    maiory = y

        self.width_var.set(str(maiorx))
        self.height_var.set(str(maiory))

        self.apply_grid()

    def show_grid_config(self):
        """Mostra dialog para configurar grade"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Configurar Grade")
            dialog.geometry("338x315")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Centralizar
            dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
            
            frame = ttk.Frame(dialog, padding="20")
            frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(frame, text="Dimensões da Grade:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
            
            # Entrada de dados
            inputs_frame = ttk.Frame(frame)
            inputs_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(inputs_frame, text="Coluna máxima:").grid(row=0, column=0, sticky="w", padx=(0, 10))
            width_entry = ttk.Entry(inputs_frame, textvariable=self.width_var, width=10)
            width_entry.grid(row=0, column=1, sticky="w")
            
            ttk.Label(inputs_frame, text="Linha máxima:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(5, 0))
            height_entry = ttk.Entry(inputs_frame, textvariable=self.height_var, width=10)
            height_entry.grid(row=1, column=1, sticky="w", pady=(5, 0))
            
            visibility_frame = ttk.LabelFrame(frame, text="Visibilidade", padding="10")
            visibility_frame.pack(fill=tk.X, pady=(15, 0))
            
            # Variável para controlar visibilidade (se não existir)
            if not hasattr(self, 'grid_visible'):
                self.grid_visible = True
            
            grid_visible_var = tk.BooleanVar(value=self.grid_visible)
            
            grid_toggle = ttk.Checkbutton(
                visibility_frame, 
                text="Mostrar linhas da grade", 
                variable=grid_visible_var,
                command=lambda: self.toggle_grid_visibility(grid_visible_var.get())
            )
            grid_toggle.pack(anchor="w")
            
            info_label = ttk.Label(
                visibility_frame, 
                text="💡 Desmarque para ocultar as linhas da grade\ne visualizar apenas com os elementos",
                font=("Segoe UI", 8),
                foreground="gray"
            )
            info_label.pack(anchor="w", pady=(5, 0))

            # Preview atual
            preview_frame = ttk.Frame(frame)
            preview_frame.pack(fill=tk.X, pady=(10, 0))
            
            current_width = self.width_var.get()
            current_height = self.height_var.get()
            preview_label = ttk.Label(preview_frame, 
                                    text=f"Configuração atual: colunas 0-{current_width}, linhas 0-{current_height}",
                                    font=("Segoe UI", 8), foreground="gray")
            preview_label.pack(anchor="w")
            
            # Botões
            btn_frame = ttk.Frame(frame)
            btn_frame.pack(fill=tk.X, pady=10)
            
            def aplicar():
                # Validar e redesenhar
                try:
                    int(self.width_var.get())
                    int(self.height_var.get())
                except ValueError:
                    messagebox.showerror("Erro", "Valores devem ser inteiros.")
                    return
                self.apply_grid()
                self.focus_trackplan_canvas()
                dialog.destroy()

            ttk.Button(btn_frame, text="Aplicar", command=aplicar).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT)
            
        except Exception as e:
            print(f"Erro no dialog de grade: {e}")

    def toggle_grid_visibility(self, visible):
        """Alterna a visibilidade das linhas da grade"""
        try:
            self.grid_visible = visible
            
            if visible:
                self.apply_grid()
            else:
                # Apagar apenas as linhas da grade, mantendo números e elementos
                self.trackplan_canvas.delete("grid")
                
            # Atualizar status na UI
            if hasattr(self, 'cell_info_var'):
                grid_status = "LIGADA" if visible else "DESLIGADA"
                current_info = self.cell_info_var.get()
                if "Grade:" in current_info:
                    # Atualizar apenas a parte da grade
                    parts = current_info.split("|")
                    if len(parts) > 0:
                        self.cell_info_var.set(f"{parts[0].strip()} | Grade: {grid_status}")
                else:
                    # Adicionar status da grade
                    if current_info:
                        self.cell_info_var.set(f"{current_info} | Grade: {grid_status}")
                    else:
                        self.cell_info_var.set(f"Grade: {grid_status}")
            
        except Exception as e:
            print(f"❌ Erro ao alternar visibilidade da grade: {e}")
            traceback.print_exc()

    def apply_grid(self):
        """Aplica a grade com números clicáveis nas margens"""
        try:
            # Valores inseridos pelo usuário são as coordenadas máximas desejadas
            max_col = int(self.width_var.get())
            max_row = int(self.height_var.get())
        except ValueError:
            messagebox.showerror("Erro", "Coluna e linha máximas devem ser números inteiros")
            return
        
        # Limpar canvas (grade, números e highlights)
        self.trackplan_canvas.delete("grid")
        self.trackplan_canvas.delete("grid_numbers")
        self.trackplan_canvas.delete("row_highlight")
        self.trackplan_canvas.delete("column_highlight")
        
        # Calcular dimensões reais
        actual_width = max_col + 1
        actual_height = max_row + 1
        
        # Configurar região de scroll
        total_width = (actual_width + 1) * self.grid_size + 100
        total_height = (actual_height + 1) * self.grid_size + 100
        self.trackplan_canvas.configure(scrollregion=(0, 0, total_width, total_height))
        
        # Desenhar linhas apenas se visível
        if getattr(self, 'grid_visible', True):
            for x in range(actual_width + 1):
                x_pos = (x + 1) * self.grid_size
                self.trackplan_canvas.create_line(
                    x_pos, self.grid_size, x_pos, (actual_height + 1) * self.grid_size,
                    fill="gray", tags="grid"
                )
            
            for y in range(actual_height + 1):
                y_pos = (y + 1) * self.grid_size
                self.trackplan_canvas.create_line(
                    self.grid_size, y_pos, (actual_width + 1) * self.grid_size, y_pos,
                    fill="gray", tags="grid"
                )
    
        # Números das colunas
        for x in range(actual_width):
            x_pos = (x + 1) * self.grid_size + self.grid_size // 2
            rect_id = self.trackplan_canvas.create_rectangle(
                (x + 1) * self.grid_size, 0, (x + 2) * self.grid_size, self.grid_size,
                fill="lightgray", outline="black", tags="grid_numbers"
            )
            text_id = self.trackplan_canvas.create_text(
                x_pos, self.grid_size // 2, text=str(x),
                font=("Arial", 8, "bold"), tags="grid_numbers"
            )
        
        # Números das linhas
        for y in range(actual_height):
            y_pos = (y + 1) * self.grid_size + self.grid_size // 2
            rect_id = self.trackplan_canvas.create_rectangle(
                0, (y + 1) * self.grid_size, self.grid_size, (y + 2) * self.grid_size,
                fill="lightgray", outline="black", tags="grid_numbers"
            )
            text_id = self.trackplan_canvas.create_text(
                self.grid_size // 2, y_pos, text=str(y),
                font=("Arial", 8, "bold"), tags="grid_numbers"
            )
        
        # Canto superior esquerdo
        corner_id = self.trackplan_canvas.create_rectangle(
            0, 0, self.grid_size, self.grid_size,
            fill="darkgray", outline="black", tags="grid_numbers"
        )
        
        grid_status = "LIGADA" if getattr(self, 'grid_visible', True) else "DESLIGADA"

    def on_tool_change(self):
        """Callback quando a ferramenta é alterada"""
        # Atualizar ângulos e mirror disponíveis para a nova ferramenta
        self.update_angle_options()
        # Atualizar preview visual
        self.update_tool_preview()
        # Focar no canvas para melhor UX
        self.focus_trackplan_canvas()

    def update_tool_preview(self):
        """Atualiza o preview da ferramenta atual"""
        try:
            # Limpar canvas
            self.preview_canvas.delete("all")
            
            tool = self.tool_var.get()
            angle = int(self.angle_var.get())
            mirror = int(self.mirror_var.get())
            
            # Detectar dimensões reais do canvas automaticamente
            self.preview_canvas.update_idletasks()  # Força atualização das dimensões
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            
            # Calcular centro real baseado nas dimensões atuais
            center_x = canvas_width // 2
            center_y = canvas_height // 2
                        
            # Atualizar texto de status (usar status_var se existir)
            tool_names = {
                "rail": "Trilho",
                "link": "Link",
                "sensor": "Sensor", 
                "switch": "Chave",
                "crossing": "Cruzamento",
                "fma": "FMA",
                "select": "Seleção",
                "eraser": "Borracha"
            }
            if tool not in ["select", "eraser"]:
                status_text = f"{tool_names.get(tool, tool)} - {angle}° - Mirror: {mirror}"
                if hasattr(self, 'status_var'):
                    self.status_var.set(status_text)
            
            # Para seleção e borracha, usar ícones simples (proporcionais ao tamanho real)
            if tool in ["select", "eraser"]:
                margin = max(2, center_x // 6)  # Margem proporcional
                if tool == "select":
                    self.preview_canvas.create_rectangle(margin, margin, canvas_width-margin, canvas_height-margin, 
                                                       outline="blue", width=2, fill="", dash=(3,3))
                elif tool == "eraser":
                    self.preview_canvas.create_rectangle(margin+2, margin+2, canvas_width-margin-2, canvas_height-margin-2, 
                                                       outline="red", width=2, fill="white")
                    self.preview_canvas.create_line(margin+2, margin+2, canvas_width-margin-2, canvas_height-margin-2, fill="red", width=2)
                    self.preview_canvas.create_line(canvas_width-margin-2, margin+2, margin+2, canvas_height-margin-2, fill="red", width=2)
                
                try:
                    self.focus_trackplan_canvas()
                except Exception as focus_error:
                    print(f"Erro ao focar canvas (select/eraser): {focus_error}")
                    import traceback
                    traceback.print_exc()
                return
            
            # Tentar usar imagem real primeiro (sistema legado consolidado)
            if self.draw_real_image_preview_consolidated(tool, angle, mirror, center_x, center_y):
                # Focar canvas após desenhar imagem real
                try:
                    self.focus_trackplan_canvas()
                except Exception as focus_error:
                    print(f"Erro ao focar canvas (imagem real): {focus_error}")
                    import traceback
                    traceback.print_exc()
                return  # Sucesso com imagem real
                
            # Fallback para desenho por linhas (sistema detalhado para elementos)
            if tool == "rail":
                self.draw_rail_preview(center_x, center_y, angle, mirror)
            elif tool == "link":
                self.draw_link_preview(center_x, center_y, angle)
            elif tool == "sensor":
                self.draw_sensor_preview(center_x, center_y, angle)
            elif tool == "switch":
                self.draw_switch_preview(center_x, center_y, angle, mirror)
            elif tool == "fma":
                self.draw_fma_preview(center_x, center_y)
            elif tool == "crossing":
                self.draw_crossing_preview(center_x, center_y, angle)
            
            # Focar o canvas do trackplan quando uma ferramenta é selecionada
            try:
                self.focus_trackplan_canvas()
            except Exception as focus_error:
                print(f"Erro ao focar canvas: {focus_error}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"Erro no preview: {e}")
            import traceback
            traceback.print_exc()
    
    def focus_trackplan_canvas(self):
        """Foca o canvas do trackplan para permitir interação imediata"""
        try:            
            # Verificar se o canvas existe
            if not hasattr(self, 'trackplan_canvas'):
                print("trackplan_canvas não existe")
                return
            
            if not self.trackplan_canvas:
                print("trackplan_canvas é None")
                return
                            
            # Certificar-se de que a aba do Designer Trackplan está selecionada
            if hasattr(self, 'notebook'):                
                # Encontrar o índice da aba do Designer Trackplan
                for i in range(self.notebook.index("end")):
                    tab_text = self.notebook.tab(i, "text")
                    
                    if "Trackplan" in tab_text or "Designer" in tab_text:
                        current_tab = self.notebook.select()
                        if current_tab != self.notebook.tabs()[i]:
                            self.notebook.select(i)
                        break
                else:
                    print("Aba Designer Trackplan não encontrada")
            else:
                print("Notebook não encontrado")
            
            # Focar o canvas
            self.trackplan_canvas.focus_set()
                            
        except Exception as e:
            print(f"Erro ao focar canvas: {e}")
            import traceback
            traceback.print_exc()
    
    def draw_real_image_preview_consolidated(self, tool, angle, mirror, center_x, center_y):
        """Desenha preview usando imagem real"""
        try:
            if not hasattr(self, 'element_images') or not self.element_images:
                return False
            
            # Gerar chave da imagem (lógica do sistema legado + novo)
            image_key = None
            
            if tool == "rail":
                image_key = f"rail_{angle}_{mirror}"
            elif tool == "link":
                image_key = f"link_{angle}"
            elif tool == "sensor":
                image_key = f"sensor_{angle}"
            elif tool == "switch":
                image_key = f"switch_{angle}_{mirror}"
            elif tool == "fma":
                # FMA usa geração dinâmica - criar imagem com texto para preview
                preview_text = "FMA"  # Texto padrão para preview
                image_key = f"fma_{angle}_{preview_text}"
                                
                # Se não existe, criar usando o sistema de geração dinâmica
                if image_key not in self.element_images:
                    dynamic_image = self.create_fma_image_with_integrated_text(angle, preview_text)
                    if dynamic_image:
                        self.element_images[image_key] = dynamic_image
                    else:
                        print(f"FMA dinâmica FALHOU para preview: {image_key}")
                        return False  # Deixar fallback handle se falhar geração
            elif tool == "crossing":
                image_key = f"crossing_{angle}"
            else:
                return False
            
            # Usar imagem se disponível
            if image_key and image_key in self.element_images:
                # Obter imagem original
                original_image = self.element_images[image_key]
                
                # Criar versão redimensionada específica para preview se não existir
                preview_key = f"preview_{image_key}"
                
                if not hasattr(self, 'preview_images'):
                    self.preview_images = {}
                
                if preview_key not in self.preview_images:
                    try:
                        from PIL import Image, ImageTk
                        
                        # Carregar a imagem original do arquivo para redimensionamento
                        images_dir = os.path.join(os.path.dirname(__file__), "images")
                        
                        # Determinar nome do arquivo baseado na chave
                        if tool == "rail":
                            filename = f"rail_{angle}_{mirror}.png"
                        elif tool == "link":
                            filename = f"link_{angle}.png"
                        elif tool == "sensor":
                            filename = f"sensor_{angle}.png"
                        elif tool == "switch":
                            filename = f"switch_{angle}_{mirror}.png"
                        elif tool == "fma":
                            pass
                        elif tool == "crossing":
                            filename = f"crossing_{angle}.png"
                        
                        # Para FMAs, sempre usar a imagem original (geração dinâmica)
                        if tool == "fma":
                            self.preview_images[preview_key] = original_image
                        else:
                            # Para outros elementos, tentar carregar arquivo físico
                            image_path = os.path.join(images_dir, filename)
                            
                            if os.path.exists(image_path):
                                # Carregar e redimensionar para preview (26x26)
                                img = Image.open(image_path)
                                preview_img = img.resize((26, 26), Image.Resampling.LANCZOS)
                                self.preview_images[preview_key] = self.create_safe_photo_image(preview_img, f"preview_{image_key}")
                            else:
                                # Se não encontrar arquivo, usar a imagem original
                                self.preview_images[preview_key] = original_image
                            
                    except ImportError:
                        # Se PIL não estiver disponível, usar imagem original
                        self.preview_images[preview_key] = original_image
                    except Exception as e:
                        print(f"Erro ao criar imagem de preview: {e}")
                        self.preview_images[preview_key] = original_image
                
                # Usar imagem de preview
                preview_image = self.preview_images.get(preview_key, original_image)
                
                # Posicionar no centro real do canvas (dinâmico)
                self.preview_canvas.create_image(center_x, center_y, image=preview_image, anchor="center")
                return True
                
            return False
            
        except Exception as e:
            print(f"Erro no preview de imagem real: {e}")
            return False
    
    def draw_rail_preview(self, x, y, angle, mirror):
        """Desenha preview de trilho usando o sistema consolidado"""
        try:
            # Usar o sistema consolidado de preview de imagens reais
            if self.draw_real_image_preview_consolidated("rail", angle, mirror, x, y):
                return  # Sucesso com imagem real
            
            # Fallback para desenho manual se imagem não disponível
            # Tamanho proporcional ao canvas (adaptável)
            canvas_size = min(self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height())
            size = max(8, canvas_size // 3)  # Pelo menos 8px, ou 1/3 do menor lado
            
            # Calcular coordenadas baseado no ângulo
            if angle == 0:  # Horizontal
                x1, y1 = x - size, y
                x2, y2 = x + size, y
            elif angle == 90:  # Vertical  
                x1, y1 = x, y - size
                x2, y2 = x, y + size
            elif angle == 45:  # Diagonal /
                x1, y1 = x - size//1.4, y + size//1.4
                x2, y2 = x + size//1.4, y - size//1.4
            elif angle == 135:  # Diagonal \
                x1, y1 = x - size//1.4, y - size//1.4
                x2, y2 = x + size//1.4, y + size//1.4
            elif angle == 180:  # Horizontal (inverso)
                x1, y1 = x + size, y
                x2, y2 = x - size, y
            elif angle == 225:  # Diagonal / (inverso)
                x1, y1 = x + size//1.4, y - size//1.4
                x2, y2 = x - size//1.4, y + size//1.4
            elif angle == 270:  # Vertical (inverso)
                x1, y1 = x, y + size
                x2, y2 = x, y - size
            elif angle == 315:  # Diagonal \ (inverso)
                x1, y1 = x + size//1.4, y + size//1.4
                x2, y2 = x - size//1.4, y - size//1.4
            else:
                x1, y1 = x - size, y
                x2, y2 = x + size, y
                
            # Desenhar linha do trilho
            self.preview_canvas.create_line(x1, y1, x2, y2, fill="black", width=2)
            
            # Indicar mirror se aplicável (pequeno círculo proporcional)
            if mirror == 1:
                circle_size = max(2, canvas_size // 15)
                self.preview_canvas.create_oval(x-circle_size, y-circle_size, x+circle_size, y+circle_size, 
                                              fill="blue", outline="darkblue")
                
        except Exception as e:
            print(f"Erro no preview do trilho: {e}")
    
    def draw_link_preview(self, x, y, angle):
        # Desenhar preview da seta
        angle = int(self.angle_var.get())
        image_key = f"link_{angle}"
        if hasattr(self, 'element_images') and image_key in self.element_images:
            self.preview_canvas.create_image(x, y, image=self.element_images[image_key], anchor="center")
        else:
            self.preview_canvas.create_line(x - 10, y, x + 10, y,
                                        arrow=tk.LAST, fill="blue", width=3)
        return

    def draw_sensor_preview(self, x, y, angle):
        """Desenha preview de sensor usando o mesmo sistema da draw_real_image_preview_consolidated"""
        try:
            # Usar o sistema consolidado de preview de imagens reais
            if self.draw_real_image_preview_consolidated("sensor", angle, 0, x, y):
                return  # Sucesso com imagem real
            
            # Fallback para desenho manual se imagem não disponível
            # Tamanho proporcional ao canvas (adaptável)
            canvas_size = min(self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height())
            size = max(6, canvas_size // 4)  # Pelo menos 6px, ou 1/4 do menor lado
            
            # Retângulo base do sensor
            self.preview_canvas.create_rectangle(x-size, y-size//2, x+size, y+size//2, 
                                                fill="yellow", outline="orange", width=1)
            
            # Linha central indicando direção
            if angle in [0, 180]:  # Horizontal
                self.preview_canvas.create_line(x-size, y, x+size, y, fill="red", width=1)
            elif angle in [90, 270]:  # Vertical
                self.preview_canvas.create_line(x, y-size//2, x, y+size//2, fill="red", width=1)
            else:  # Diagonal
                self.preview_canvas.create_line(x-size//2, y-size//4, x+size//2, y+size//4, fill="red", width=1)
                
        except Exception as e:
            print(f"Erro no preview do sensor: {e}")
            # Fallback mínimo em caso de erro
            self.preview_canvas.create_oval(x-5, y-5, x+5, y+5, fill="yellow", outline="orange")

    def draw_crossing_preview(self, x, y, angle):
        """Preview do cruzamento (usa imagem real se disponível; fallback desenha um '+')."""
        try:
            if self.draw_real_image_preview_consolidated("crossing", angle, 0, x, y):
                return
            # Fallback: desenhar cruz (linhas horizontal e vertical)
            size = max(8, min(self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height()) // 3)
            self.preview_canvas.create_line(x - size, y, x + size, y, fill="black", width=2)
            self.preview_canvas.create_line(x, y - size, x, y + size, fill="black", width=2)
        except Exception as e:
            print(f"Erro no preview do cruzamento: {e}")

    def draw_switch_preview(self, x, y, angle, mirror):
        """Desenha preview de chave"""
        try:
            # Tamanho proporcional ao canvas (adaptável)
            canvas_size = min(self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height())
            size = max(7, canvas_size // 3)  # Pelo menos 7px, ou 1/3 do menor lado
            
            # Linha principal
            if angle == 0:  # Horizontal
                self.preview_canvas.create_line(x-size, y, x+size, y, fill="black", width=2)
                # Linha de desvio
                if mirror == 0:
                    self.preview_canvas.create_line(x, y, x+size//2, y-size//2, fill="green", width=1)
                else:
                    self.preview_canvas.create_line(x, y, x+size//2, y+size//2, fill="green", width=1)
            elif angle == 90:  # Vertical
                self.preview_canvas.create_line(x, y-size, x, y+size, fill="black", width=2)
                # Linha de desvio
                if mirror == 0:
                    self.preview_canvas.create_line(x, y, x+size//2, y+size//2, fill="green", width=1)
                else:
                    self.preview_canvas.create_line(x, y, x-size//2, y+size//2, fill="green", width=1)
            else:  # Outras orientações - desenho simplificado
                self.preview_canvas.create_line(x-size, y, x+size, y, fill="black", width=2)
                self.preview_canvas.create_line(x, y, x+size//2, y-size//2, fill="green", width=1)
            
            # Pequeno círculo indicando ponto de controle (proporcional)
            circle_size = max(2, canvas_size // 15)
            self.preview_canvas.create_oval(x-circle_size, y-circle_size, x+circle_size, y+circle_size, 
                                          fill="red", outline="darkred")
            
        except Exception as e:
            print(f"Erro no preview da chave: {e}")
            
    def draw_fma_preview(self, x, y):
        """Desenha preview de FMA (fallback quando geração dinâmica falha)"""
        try:
            # Tamanho proporcional ao canvas (adaptável)
            canvas_size = min(self.preview_canvas.winfo_width(), self.preview_canvas.winfo_height())
            size = max(7, canvas_size // 3)  # Pelo menos 7px, ou 1/3 do menor lado
            
            # Retângulo de FMA - CORES NORMAIS (não azuis)
            self.preview_canvas.create_rectangle(x-size, y-size//2, x+size, y+size//2, 
                                                fill="white", outline="black", width=1)
            
            # Texto FMA - COR NORMAL (não azul), tamanho de fonte proporcional
            font_size = max(6, canvas_size // 5)
            self.preview_canvas.create_text(x, y, text="FMA", font=("Arial", font_size, "bold"), fill="black")
            
        except Exception as e:
            print(f"Erro no preview do FMA: {e}")
    
    def setup_trackplan_events(self):
        """Configura todos os eventos do trackplan"""
        try:
            # Eventos do canvas com foco automático
            self.trackplan_canvas.bind("<Button-1>", self.on_canvas_click_with_focus)
            self.trackplan_canvas.bind("<Motion>", self.on_canvas_motion)
            self.trackplan_canvas.bind("<Button-3>", self.on_grid_right_click)
            self.trackplan_canvas.bind("<MouseWheel>", self.on_mouse_wheel)
            
            # Tornar canvas focável para receber eventos de teclado
            self.trackplan_canvas.focus_set()
            self.trackplan_canvas.bind("<Key>", self.on_canvas_key)
            self.trackplan_canvas.bind("<KeyPress>", self.on_canvas_key)            
        except Exception as e:
            print(f"Erro ao configurar eventos: {e}")

    def restore_canvas_bindings(self):
        """Restaura os bindings padrão do canvas e aplica foco."""
        try:
            self.trackplan_canvas.bind("<Button-1>", self.on_canvas_click_with_focus)
            self.trackplan_canvas.bind("<Motion>", self.on_canvas_motion)
            self.trackplan_canvas.bind("<Button-3>", self.on_grid_right_click)
            self.trackplan_canvas.bind("<MouseWheel>", self.on_mouse_wheel)
            self.trackplan_canvas.focus_set()
        except Exception as e:
            print(f"Erro ao restaurar bindings do canvas: {e}")

    def on_canvas_click_with_focus(self, event):
        """Evento de clique no canvas com foco automático"""
        self.trackplan_canvas.focus_set()
        return self.on_canvas_click(event)
    
    def initialize_trackplan_system(self):
        """Inicializa o sistema do trackplan"""
        try:
            # Variáveis de controle do sistema
            self.trackplan_elements = []  # Lista para armazenar elementos
            self.selected_elements = []  # Lista de elementos selecionados
            self.clipboard = []  # Área de transferência
            self.undo_stack = []  # Pilha de undo
            self.redo_stack = []  # Pilha de redo
            self.max_undo = 50  # Máximo de operações de undo
            
            # Variáveis para seleção de linhas/colunas
            self.selected_rows = set()  # Linhas selecionadas
            self.selected_columns = set()  # Colunas selecionadas
            self.row_column_clipboard = {'type': None, 'data': None}  # Clipboard para linhas/colunas
            
            # Variáveis de estado de edição
            self.is_dragging = False
            self.drag_start = None
            self.selection_rect = None
            
            # Variáveis da grade
            self.grid_width = 30
            self.grid_height = 10
            self.cell_size = 20
            self.grid_size = 30  # Tamanho das células na visualização
            self.grid_visible = True 
            
            # Mapeamento de elementos por posição para busca rápida
            self.element_position_map = {}
            
            #Animação seleção cubicle
            self._overlay_anim = {}  # tag -> {'base': (x1,y1,x2,y2), 'step': 0, 'job': None}

            # ID sequencial para elementos
            self.next_element_id = 7000
            self.next_sensor_id = 2000
            self.next_fma_id = 3000
            
            # Configuração de ângulos e mirrors automáticos de rail para sensores e FMAs
            self.auto_rail_config = {
                # Configuração para sensores: ângulo_sensor -> (ângulo_rail, mirror_rail)
                'sensor': {
                    0: (0, 0),       # Sensor 0° → Rail 0° mirror 0
                    45: (270, 0),     # Sensor 45° → Rail 270° mirror 0
                    90: (180, 0),     # Sensor 90° → Rail 180° mirror 0
                    135: (270, 1),   # Sensor 135° → Rail 270° mirror 1
                    180: (0, 0),   # Sensor 180° → Rail 0° mirror 0
                    225: (270, 0),   # Sensor 225° → Rail 270° mirror 0
                    270: (180, 0),   # Sensor 270° → Rail 180° mirror 0
                    315: (270, 1)    # Sensor 315° → Rail 270° mirror 1
                },
                # Configuração para FMAs: ângulo_fma -> (ângulo_rail, mirror_rail)
                'fma': {
                    0: (0, 0),       # FMA 0° → Rail 0° mirror 0
                    90: (180, 0),     # FMA 90° → Rail 180° mirror 0
                    180: (0, 0),   # FMA 180° → Rail 0° mirror 0
                    270: (180, 0),   # FMA 270° → Rail 180° mirror 0
                }
            }
            
            # Carregar imagens dos elementos
            self.load_element_images()            
        except Exception as e:
            print(f"Erro ao inicializar sistema trackplan: {e}")
    
    def get_auto_rail_config(self, element_type, element_angle):
        """Calcula o ângulo e mirror automáticos do rail baseado no tipo e ângulo do elemento (sensor/FMA)"""
        try:
            if element_type in self.auto_rail_config:
                config = self.auto_rail_config[element_type].get(element_angle, (element_angle, 0))
                return config  # Retorna (ângulo, mirror)
            return (element_angle, 0)  # Fallback para o próprio ângulo com mirror 0
        except Exception as e:
            print(f"Erro ao calcular configuração automática do rail: {e}")
            return (element_angle, 0)
    

    def add_automatic_rail_for_element(self, grid_x, grid_y, element_type, element_angle, element_id=None):
        """Adiciona automaticamente um rail para sensor ou FMA - APENAS NO CÓDIGO para XML"""
        try:
            # Calcular ângulo e mirror do rail
            rail_angle, rail_mirror = self.get_auto_rail_config(element_type, element_angle)
            
            # Verificar se já existe rail automático na posição
            existing_auto_rail = None
            for element in self.trackplan_elements:
                if (element.get("type") == "rail" and 
                    element.get("x") == grid_x and 
                    element.get("y") == grid_y and
                    element.get("auto_rail") == True):
                    existing_auto_rail = element
                    break
            
            if existing_auto_rail:
                # Atualizar apenas os dados do rail automático
                existing_auto_rail["angle"] = rail_angle
                existing_auto_rail["mirror"] = rail_mirror
                existing_auto_rail["parent_element"] = element_id
                existing_auto_rail["parent_type"] = element_type

                return existing_auto_rail
            else:                
                # Criar elemento de rail APENAS COM DADOS

                element_id_rail = self.next_element_id

                if ((self.next_element_id + 1) == 8000):
                    self.next_element_id = 71000
                else:
                    self.next_element_id += 1

                rail_element = {
                    "type": "rail",
                    "id": element_id_rail,
                    "x": grid_x,
                    "y": grid_y,
                    "angle": rail_angle,
                    "mirror": rail_mirror,
                    "rail_type": None,
                    "auto_rail": True,
                    "parent_element": element_id,
                    "parent_type": element_type,
                    "canvas_ids": None,
                    "canvas_id": None,
                    "original_image_key": None
                }    

                # Adicionar à lista de elementos (sem desenhar no canvas)
                self.trackplan_elements.append(rail_element)

                return rail_element
                
        except Exception as e:
            print(f"Erro ao adicionar rail automático: {e}")
            return None

    def has_element_at_position(self, x, y):
        """Verifica se há elemento na posição especificada"""
        try:
            for element in self.trackplan_elements:
                if element.get('x') == x and element.get('y') == y:
                    return True
            return False
        except:
            return False
    
    def get_element_at_position(self, x, y):
        """Retorna elemento na posição especificada (prioriza elementos reais, ignora auto_rails)"""
        try:
            # prioridade ao último desenhado (reversed)
            for e in reversed(getattr(self, 'trackplan_elements', [])):
                if e.get('x') == x and e.get('y') == y and not e.get('auto_rail'):
                    return e
        except Exception:
            pass
        return None

    def _build_clean_state(self):
        """Monta um snapshot serializável do estado atual (sem objetos Tk/PhotoImage)."""
        try:
            clean_elements = []
            for e in getattr(self, 'trackplan_elements', []):
                if not isinstance(e, dict):
                    continue
                # Copiar apenas campos serializáveis; remover refs a objetos Tk/PhotoImage
                ce = {}
                for k, v in e.items():
                    # Campos problemáticos conhecidos
                    if k in ('current_image',):
                        continue
                    # Evitar objetos Tk em geral (widgets, images, etc.)
                    v_type = type(v).__name__
                    if v_type in ('PhotoImage',):
                        continue
                    ce[k] = v
                # Deepcopy agora é seguro
                clean_elements.append(copy.deepcopy(ce))

            gw = str(getattr(self, 'width_var', tk.StringVar(value="30")).get())
            gh = str(getattr(self, 'height_var', tk.StringVar(value="10")).get())

            state = {
                'elements': clean_elements,
                'grid_width': gw,
                'grid_height': gh,
                'next_element_id': getattr(self, 'next_element_id', 7001),
                'element_position_map': copy.deepcopy(getattr(self, 'element_position_map', {})),
            }
            return state
        except Exception as e:
            print(f"_build_clean_state: {e}")
            # Fallback mínimo
            return {
                'elements': [],
                'grid_width': "30",
                'grid_height': "10",
                'next_element_id': getattr(self, 'next_element_id', 7001),
                'element_position_map': {},
            }

    def save_state_for_undo(self):
        """Salva estado atual para operação de undo filtrando objetos não-copiáveis"""
        try:
            if not hasattr(self, 'undo_stack'):
                self.undo_stack = []
            if not hasattr(self, 'redo_stack'):
                self.redo_stack = []
            
            # Evitar saves reentrantes/nested
            if getattr(self, '_saving_state', False):
                return
            self._saving_state = True

            state = self._build_clean_state()

            # Dedupe simples: evita empilhar estados idênticos
            if self.undo_stack and self.undo_stack[-1].get('elements') == state.get('elements'):
                return

            self.undo_stack.append(state)
            if len(self.undo_stack) > 50:
                self.undo_stack.pop(0)

            self.redo_stack.clear()
        except Exception as e:
            print(f"Erro ao salvar estado para undo: {e}")
        finally:
            self._saving_state = False
    
    def handle_selection_click(self, grid_x, grid_y, event):
        """Gerencia clique da ferramenta de seleção"""
        try:
            # Verificar teclas modificadoras
            ctrl_pressed = (event.state & 0x4) != 0
            shift_pressed = (event.state & 0x1) != 0
            
            # CTRL + SHIFT + CLIQUE = Seleção em área/intervalo
            if ctrl_pressed and shift_pressed:
                self.handle_area_selection(grid_x, grid_y)
                return
            
            # Procurar elemento na posição clicada
            clicked_element = None
            for element in self.trackplan_elements:
                if element.get('x') == grid_x and element.get('y') == grid_y:
                    clicked_element = element
                    break
            
            if clicked_element:
                # Seleção de elemento existente
                is_selected = self.is_element_selected(clicked_element)
                
                if is_selected:
                    # Desselecionar elemento
                    self.deselect_element(clicked_element)
                else:
                    # Se não há Ctrl, limpar seleção anterior
                    if not ctrl_pressed:
                        self.clear_selection()
                    
                    # Selecionar elemento
                    self.select_element(clicked_element)
            else:

                if ctrl_pressed:
                    # Multi-seleção de célula vazia
                    self.toggle_empty_cell_selection(grid_x, grid_y)
                else:
                    # Seleção única de célula vazia
                    self.clear_selection()
                    self.select_empty_cell(grid_x, grid_y)
            
            # Atualizar info de seleção
            self.update_selection_info()
            
        except Exception as e:
            print(f"Erro na seleção: {e}")
            import traceback
            traceback.print_exc()
    
    def handle_area_selection(self, grid_x, grid_y):
        """Gerencia seleção em área usando Ctrl+Shift+Clique"""
        try:
            # Inicializar last_click_position se não existir
            if not hasattr(self, 'last_click_position') or self.last_click_position is None:
                # Primeiro clique: armazenar posição e destacar
                self.last_click_position = (grid_x, grid_y)
                self.clear_selection()
                
                # Selecionar a posição inicial
                element = self.get_element_at_position(grid_x, grid_y)
                if element:
                    self.select_element(element)
                else:
                    self.select_empty_cell(grid_x, grid_y)
                
                # Feedback visual para o primeiro ponto
                self.show_first_point_feedback(grid_x, grid_y)
                return
            
            # Segundo clique: selecionar área entre os dois pontos
            start_x, start_y = self.last_click_position
            end_x, end_y = grid_x, grid_y
                        
            # Calcular limites da área (ordem crescente)
            min_x, max_x = min(start_x, end_x), max(start_x, end_x)
            min_y, max_y = min(start_y, end_y), max(start_y, end_y)
            
            # Limpar seleção anterior
            self.clear_selection()
            
            # Selecionar tudo na área retangular (elementos E células vazias)
            selected_count = 0
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    element = self.get_element_at_position(x, y)
                    if element:
                        # Há elemento na posição
                        self.select_element(element)
                        selected_count += 1
                    else:
                        # Posição vazia
                        self.select_empty_cell(x, y)
                        selected_count += 1
            
            # Resetar last_click_position para próxima seleção
            self.last_click_position = None
            
            # Calcular dimensões da área
            width = max_x - min_x + 1
            height = max_y - min_y + 1
            
            # Atualizar info de seleção
            self.update_selection_info()
            
            # Feedback visual temporário da área completa
            self.show_area_selection_feedback(min_x, min_y, max_x, max_y)
            
        except Exception as e:
            print(f"Erro na seleção em área: {e}")
            import traceback
            traceback.print_exc()
    
    def select_position(self, grid_x, grid_y):
        """Seleciona uma posição específica (elemento ou célula vazia)"""
        # Procurar elemento na posição
        element = None
        for elem in self.trackplan_elements:
            if elem.get('x') == grid_x and elem.get('y') == grid_y:
                element = elem
                break
        
        if element:
            # Selecionar elemento existente
            self.select_element(element)
        else:
            # Selecionar célula vazia
            self.select_empty_cell(grid_x, grid_y)
    
    def show_first_point_feedback(self, grid_x, grid_y):
        """Mostra feedback visual para o primeiro ponto da seleção em área"""
        try:
            # Calcular posição no canvas
            canvas_x = (grid_x + 1) * self.grid_size
            canvas_y = (grid_y + 1) * self.grid_size
            
            # Remover feedback anterior se existir
            self.trackplan_canvas.delete("first_point_feedback")
            
            # Criar cruz indicando o primeiro ponto
            self.trackplan_canvas.create_line(
                canvas_x, canvas_y, 
                canvas_x + self.grid_size, canvas_y + self.grid_size,
                fill="orange", width=3, tags="first_point_feedback"
            )
            self.trackplan_canvas.create_line(
                canvas_x + self.grid_size, canvas_y, 
                canvas_x, canvas_y + self.grid_size,
                fill="orange", width=3, tags="first_point_feedback"
            )
            
            # Pequeno círculo no centro
            center_x = canvas_x + self.grid_size // 2
            center_y = canvas_y + self.grid_size // 2
            self.trackplan_canvas.create_oval(
                center_x - 5, center_y - 5, center_x + 5, center_y + 5,
                fill="orange", outline="darkorange", width=2, tags="first_point_feedback"
            )
            
        except Exception as e:
            print(f"Erro no feedback do primeiro ponto: {e}")

    def show_area_selection_feedback(self, min_x, min_y, max_x, max_y):
        """Mostra feedback visual temporário da área selecionada (cores neutras)."""
        try:
            # Remover feedback anterior
            self.trackplan_canvas.delete("area_feedback")
            self.trackplan_canvas.delete("first_point_feedback")

            # Calcular posição no canvas
            canvas_x1 = (min_x + 1) * self.grid_size
            canvas_y1 = (min_y + 1) * self.grid_size
            canvas_x2 = (max_x + 2) * self.grid_size
            canvas_y2 = (max_y + 2) * self.grid_size

            # Contorno cinza
            feedback_id = self.trackplan_canvas.create_rectangle(
                canvas_x1, canvas_y1, canvas_x2, canvas_y2,
                outline="darkgray", width=2, fill="", dash=(8, 4),
                tags="area_feedback"
            )

            # Texto informativo cinza
            center_x = (canvas_x1 + canvas_x2) // 2
            center_y = (canvas_y1 + canvas_y2) // 2
            width = max_x - min_x + 1
            height = max_y - min_y + 1

            text_id = self.trackplan_canvas.create_text(
                center_x, center_y,
                text=f"Área {width}x{height}\nselecionada",
                font=("Arial", 10, "bold"),
                fill="darkgray", tags="area_feedback"
            )

            # Remover feedback após 3 segundos
            self.root.after(3000, lambda: self.trackplan_canvas.delete("area_feedback"))
        except Exception as e:
            print(f"Erro ao feedback visual: {e}")
    
    def is_element_selected(self, element):
        """Verifica se um elemento está selecionado"""
        if not hasattr(self, 'selected_elements'):
            self.selected_elements = []
        
        for selected in self.selected_elements:
            # Verificar se é um elemento (dict) e não célula vazia (tuple)
            if isinstance(selected, dict) and isinstance(element, dict):
                if (selected.get('id') == element.get('id') and 
                    selected.get('type') == element.get('type')):
                    return True
        return False
    
    def select_element(self, element):
        """Seleciona um elemento"""
        if not hasattr(self, 'selected_elements'):
            self.selected_elements = []
        
        # Evitar duplicatas
        if not self.is_element_selected(element):
            self.selected_elements.append(element)
            self.highlight_element_for_selection(element)
    
    def deselect_element(self, element):
        """Desseleciona um elemento"""
        if not hasattr(self, 'selected_elements'):
            self.selected_elements = []
        
        # Remover da lista e destacar - apenas elementos (dict), não células vazias (tuple)
        elements_to_remove = []
        for selected in self.selected_elements:
            # Verificar se é um elemento (dict) e não célula vazia (tuple)
            if isinstance(selected, dict) and isinstance(element, dict):
                if (selected.get('id') == element.get('id') and 
                    selected.get('type') == element.get('type')):
                    elements_to_remove.append(selected)
        
        for elem in elements_to_remove:
            self.selected_elements.remove(elem)
            self.unhighlight_element(elem)
    
    def clear_selection(self):
        """Limpa toda a seleção"""
        if not hasattr(self, 'selected_elements'):
            self.selected_elements = []
            return
        
        # Remover destaque de todos os elementos e células vazias
        for item in self.selected_elements:
            if isinstance(item, dict):  # Elemento
                self.unhighlight_element(item)
            elif isinstance(item, tuple):  # Célula vazia (x, y)
                grid_x, grid_y = item
                self.unhighlight_empty_cell(grid_x, grid_y)
        
        self.selected_elements.clear()
    
    def highlight_element_for_selection(self, element):
        """Destaca um elemento visualmente com contorno vermelho para seleção (sem overlay azul)."""
        try:
            # Calcular posição no canvas (considerando offset das coordenadas)
            canvas_x = (element['x'] + 1) * self.grid_size
            canvas_y = (element['y'] + 1) * self.grid_size

            # Remover qualquer overlay anterior do mesmo elemento (se houver)
            if 'overlay_tag' in element:
                # Compatível com estados antigos; agora não criamos overlay
                self.remove_selection_overlay_by_tag(element['overlay_tag'])
                del element['overlay_tag']

            # Criar retângulo de destaque apenas em vermelho (sem overlay azul)
            highlight_id = self.trackplan_canvas.create_rectangle(
                canvas_x, canvas_y,
                canvas_x + self.grid_size, canvas_y + self.grid_size,
                outline="red", width=3, fill="", tags="selection_highlight"
            )

            element['highlight_id'] = highlight_id
        except Exception as e:
            print(f"Erro ao destacar elemento: {e}")

    # === Destaque verde para modo de seleção de trilhos da FMA ===
    def _highlight_element_for_pick(self, element):
        """Destaca um elemento com contorno verde (modo pick)."""
        try:
            canvas_x = (element['x'] + 1) * self.grid_size
            canvas_y = (element['y'] + 1) * self.grid_size
            # Remover anterior se existir
            if 'pick_highlight_id' in element:
                try:
                    self.trackplan_canvas.delete(element['pick_highlight_id'])
                except Exception:
                    pass
            pick_id = self.trackplan_canvas.create_rectangle(
                canvas_x, canvas_y,
                canvas_x + self.grid_size, canvas_y + self.grid_size,
                outline="green", width=3, fill="", tags="fma_pick"
            )
            element['pick_highlight_id'] = pick_id
        except Exception as e:
            print(f"Erro ao destacar (pick): {e}")

    def _unhighlight_element_for_pick(self, element):
        try:
            if 'pick_highlight_id' in element:
                try:
                    self.trackplan_canvas.delete(element['pick_highlight_id'])
                except Exception:
                    pass
                element.pop('pick_highlight_id', None)
        except Exception as e:
            print(f"Erro ao remover destaque (pick): {e}")
    
    def unhighlight_element(self, element):
        """Remove o destaque de um elemento"""
        try:
            if 'highlight_id' in element:
                self.trackplan_canvas.delete(element['highlight_id'])
                del element['highlight_id']
            # Remover overlay animado (se existir)
            if 'overlay_tag' in element:
                self.remove_selection_overlay_by_tag(element['overlay_tag'])
                del element['overlay_tag']
        except Exception as e:
            print(f"Erro ao remover destaque: {e}")
    
    def update_selection_info(self):
        """Atualiza as informações de seleção na interface"""
        try:
            if not hasattr(self, 'selected_elements'):
                self.selected_elements = []
            
            # Separar elementos de células vazias
            elements = [sel for sel in self.selected_elements if isinstance(sel, dict)]
            empty_cells = [sel for sel in self.selected_elements if isinstance(sel, tuple)]

            element_count = len(elements)
            cell_count = len(empty_cells)
            total_count = element_count + cell_count
            
            if total_count == 0:
                info_text = ""
            elif total_count == 1:
                if element_count > 0:
                    element = elements[0]
                    coord = f"({element['x']}, {element['y']})"
                    info_text = f"Selecionado: {element.get('type', 'elemento')} em {coord}     |   ID: {element.get('id', 'ID desconhecido')}"
                else:
                    cell = empty_cells[0]
                    info_text = f"Selecionada: célula vazia em ({cell[0]}, {cell[1]})"
            else:
                if element_count > 0 and cell_count > 0:
                    info_text = f"Selecionados: {element_count} elementos + {cell_count} células vazias"
                elif element_count > 0:
                    info_text = f"Selecionados: {element_count} elementos"
                else:
                    info_text = f"Selecionadas: {cell_count} células vazias"
            
            # Atualizar label de seleção se existir
            if hasattr(self, 'selection_info_var'):
                self.selection_info_var.set(info_text)
                
        except Exception as e:
            print(f"Erro ao atualizar info de seleção: {e}")

    def remove_selection_overlay_by_tag(self, tag):
        """Cancela a animação e remove o overlay vinculado ao 'tag'."""
        try:
            if tag in self._overlay_anim:
                job = self._overlay_anim[tag].get('job')
                if job:
                    try:
                        self.root.after_cancel(job)
                    except Exception:
                        pass
                del self._overlay_anim[tag]
            # Remover objetos do canvas associados ao tag
            try:
                self.trackplan_canvas.delete(tag)
            except Exception:
                pass
        except Exception as e:
            print(f"Erro remove_selection_overlay_by_tag: {e}")
    
    def select_empty_cell(self, grid_x, grid_y):
        """Seleciona uma célula vazia"""
        try:            
            # Usar tupla (x, y) para representar célula vazia
            empty_cell = (grid_x, grid_y)
            
            if not hasattr(self, 'selected_elements'):
                self.selected_elements = []
            
            # Verificar se já está selecionada
            if empty_cell not in self.selected_elements:
                self.selected_elements.append(empty_cell)
                self.highlight_empty_cell(grid_x, grid_y)
            
        except Exception as e:
            print(f"❌ Erro ao selecionar célula vazia: {e}")
            import traceback
            traceback.print_exc()
    
    def toggle_empty_cell_selection(self, grid_x, grid_y):
        """Alterna seleção de célula vazia"""
        try:
            empty_cell = (grid_x, grid_y)
            
            if not hasattr(self, 'selected_elements'):
                self.selected_elements = []
            
            if empty_cell in self.selected_elements:
                self.selected_elements.remove(empty_cell)
                self.unhighlight_empty_cell(grid_x, grid_y)
            else:
                self.selected_elements.append(empty_cell)
                self.highlight_empty_cell(grid_x, grid_y)
                
        except Exception as e:
            print(f"Erro ao alternar seleção de célula vazia: {e}")
    
    def highlight_empty_cell(self, grid_x, grid_y):
        """Destaca uma célula vazia com retângulo cinza (sem overlay azul)."""
        try:
            canvas_x = (grid_x + 1) * self.grid_size
            canvas_y = (grid_y + 1) * self.grid_size
            x1, y1 = canvas_x, canvas_y
            x2, y2 = canvas_x + self.grid_size, canvas_y + self.grid_size

            tag = f"empty_highlight_{grid_x}_{grid_y}"
            # Retângulo cinza tracejado, sem overlay/anim
            self.trackplan_canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="gray", width=2, fill="", dash=(4, 2),
                tags=tag
            )
        except Exception as e:
            print(f"Erro ao destacar célula vazia: {e}")

    def unhighlight_empty_cell(self, grid_x, grid_y):
        """Remove destaque de célula vazia."""
        try:
            tag = f"empty_highlight_{grid_x}_{grid_y}"
            # Remover o retângulo cinza (novo comportamento)
            self.trackplan_canvas.delete(tag)
            # Compatível com overlay antigo (não usados mais)
            self.remove_selection_overlay_by_tag(tag)
        except Exception as e:
            print(f"Erro ao remover destaque de célula vazia: {e}")

    def copy_element(self, element):
        """Copia elemento"""
        try:
            import copy
            self.clipboard = [copy.deepcopy(element)]
        except Exception as e:
            print(f"Erro ao copiar elemento: {e}")
    
    def on_canvas_key(self, event):
        """Manipula teclas pressionadas no canvas"""
        try:
            x = self.trackplan_canvas.canvasx(event.x)
            y = self.trackplan_canvas.canvasy(event.y)
            grid_x = int((x - self.grid_size) // self.grid_size)
            grid_y = int((y - self.grid_size) // self.grid_size)

            key = event.keysym.lower()
            ctrl_pressed = bool(event.state & 0x4)
            shift_pressed = bool(event.state & 0x1)
            modifier_keys = ['control_l', 'control_r', 'shift_l', 'shift_r', 'alt_l', 'alt_r', 
                           'meta_l', 'meta_r', 'super_l', 'super_r']
            if key in modifier_keys:
                return
            
            # Atalhos de edição com Ctrl
            if ctrl_pressed:
                if key == 'c':
                    self.copy_selection()
                    return  # Importante: sair imediatamente
                elif key == 'x':
                    self.cut_selection()
                    return
                elif key == 'v':
                    self.paste_selection()
                    return
                elif key == 'z':
                    self.undo_action()
                    return
                elif key == 'y':
                    self.redo_action()
                    return
                elif key == 'f':
                    self.open_fma_editor()
                    return
                elif key == 's':
                    self.open_sensor_editor()
                    return
                elif key == 'a':
                    self.select_all()
                    return
                elif key == 'o':
                    self.load_trackplan()           
                    return
                elif key == 'b':
                    self.save_trackplan()
                    return
                elif key == 'l':
                    self.edit_link()
                    return
                elif key == 'e':
                    self.open_fma_test()
                    return
                else:
                    return
                        
            if key in ("up", "down", "left", "right"):
                self.extend_selection_by_arrow(key)
                return

            # Atalhos de ferramentas (apenas SEM Ctrl)
            if key == 'escape':
                self.clear_selection()
                self.update_selection_info()
                return
            elif key == 't':
                self.set_tool_shortcut("rail")
                return
            elif key == 's':
                self.set_tool_shortcut("sensor")
                return
            elif key == 'l':
                self.set_tool_shortcut("link")
                return
            elif key == 'c':
                self.set_tool_shortcut("switch")
                return
            elif key == 'f':
                self.set_tool_shortcut("fma")
                return
            elif key == 'v':
                self.set_tool_shortcut("select")
                return
            elif key == 'e':
                self.set_tool_shortcut("eraser")
                return
            elif key == 'm':
                self.toggle_mirror_shortcut()
                return
            elif key == 'delete':
                self.delete_selected_elements()
                return
            elif key == 'x':
                self.set_tool_shortcut("crossing")
            else:
                return
            
        except Exception as e:
            print(f"Erro no evento de tecla: {e}")
            import traceback
            traceback.print_exc()
        
    def _get_selection_anchor(self):
        """Retorna (x, y) da última seleção para navegação por teclado."""
        if not getattr(self, "selected_elements", None):
            return None

        last = self.selected_elements[-1]
        if isinstance(last, dict):
            return int(last.get("x", 0)), int(last.get("y", 0))
        if isinstance(last, tuple) and len(last) == 2:
            return int(last[0]), int(last[1])
        return None

    def _get_grid_limits(self):
        """Retorna limites máximos da grade (max_x, max_y)."""
        try:
            max_x = int(self.width_var.get())
            max_y = int(self.height_var.get())
        except Exception:
            max_x, max_y = 71, 16
        return max_x, max_y

    def extend_selection_by_arrow(self, direction):
        """Expande seleção para a célula vizinha na direção informada."""
        anchor = self._get_selection_anchor()
        if anchor is None:
            # Sem seleção prévia: começa em (0,0)
            anchor = (0, 0)

        x, y = anchor
        dx, dy = 0, 0
        if direction == "up":
            dy = -1
        elif direction == "down":
            dy = 1
        elif direction == "left":
            dx = -1
        elif direction == "right":
            dx = 1

        nx, ny = x + dx, y + dy
        max_x, max_y = self._get_grid_limits()

        # respeitar limites
        if nx < 0 or ny < 0 or nx > max_x or ny > max_y:
            return

        # Mantem apenas um item selecionado
        self.clear_selection()
        elem = self.get_element_at_position(nx, ny)

        if elem:
            self.select_element(elem)
        else:
            self.select_empty_cell(nx, ny)

        self.update_selection_info()

    # === MÉTODOS AUXILIARES PARA TRACKPLAN ===
    def toggle_mirror_shortcut(self):
        """Alterna o mirror através de atalho de teclado"""
        try:
            current_tool = self.tool_var.get()
            current_angle = int(self.angle_var.get())
            if current_tool in ['fma', 'sensor', 'crossing', 'link']:
                return
            if current_tool == 'rail' and current_angle in [0, 180]:
                return
            
            if hasattr(self, 'mirror_var'):
                current = self.mirror_var.get()
                new_value = "1" if current == "0" else "0"
                self.mirror_var.set(new_value)
                self.update_tool_preview()
        except Exception as e:
            print(f"Erro ao alternar mirror: {e}")
    
    def copy_selection(self):
        """Copia a seleção atual"""
        try:
            if not hasattr(self, 'selected_elements') or not self.selected_elements:
                messagebox.showinfo("Aviso", "Nenhum elemento selecionado para copiar.")
                return
            
            # Filtrar apenas elementos reais e ignorar rails automáticos
            filtered_elements = []
            for item in self.selected_elements:
                if isinstance(item, dict):
                    if item.get('type') == 'rail' and item.get('auto_rail'):
                        continue
                    filtered_elements.append(item)
            
            if not filtered_elements:
                messagebox.showinfo("Aviso", "Nenhum elemento válido selecionado para copiar.")
                return
            
            # Criar cópias limpas sem refs de canvas
            copied_elements = []
            for element in filtered_elements:
                safe = {k: v for k, v in element.items()
                        if k not in ('canvas_id','canvas_ids','diag_id','symbol_id','text_id','highlight_id','pick_highlight_id')}
                copied_elements.append(copy.deepcopy(safe))
            
            # Origem (menor x,y)
            min_x = min(e.get('x', 0) for e in copied_elements)
            min_y = min(e.get('y', 0) for e in copied_elements)
            self.clipboard = {'elements': copied_elements, 'origin': (min_x, min_y)}
        except Exception as e:
            print(f"Erro ao copiar seleção: {e}")
            messagebox.showerror("Erro", f"Erro ao copiar seleção: {e}")
        
    def cut_selection(self):
        """Recorta a seleção atual"""
        try:
            if not hasattr(self, 'selected_elements') or not self.selected_elements:
                messagebox.showinfo("Info", "Nenhum elemento selecionado para recortar")
                return
            
            # Primeiro copiar (isso já filtra corretamente)
            self.copy_selection()
            
            # Filtrar apenas elementos reais antes de deletar
            elements_to_delete = []
            
            for item in self.selected_elements:
                # Verificar se é um elemento real (dict) e não célula vazia (tuple)
                if isinstance(item, dict):
                    # Encontrar o elemento real na lista para garantir que ainda existe
                    for trackplan_element in self.trackplan_elements:
                        if (trackplan_element.get('id') == item.get('id') and 
                            trackplan_element.get('type') == item.get('type') and
                            trackplan_element.get('x') == item.get('x') and
                            trackplan_element.get('y') == item.get('y')):
                            elements_to_delete.append(trackplan_element)
                            break          

            # Deletar apenas os elementos reais (um undo por item)
            for element in elements_to_delete:
                try:
                    # snapshot por elemento
                    self.save_state_for_undo()
                    # Verificar se elemento ainda existe antes de tentar deletar
                    if element in self.trackplan_elements:
                        # Verificar se é um sensor ou FMA com rail automático associado
                        if element.get("type") in ["sensor", "fma"]:
                            self.remove_auto_rail_when_parent_deleted(element)
                        
                        # Remover completamente do canvas e da lista
                        self.delete_element_completely(element)
                        
                        # Remover da lista de elementos
                        self.trackplan_elements.remove(element)
                        
                    else:
                        print(f"Elemento já não existe na lista: {element.get('type')} ID {element.get('id')}")
                        
                except Exception as e:
                    print(f"Erro ao deletar elemento individual: {e}")
            
            # Limpar seleção
            self.clear_selection()
            
        except Exception as e:
            print(f"Erro ao recortar: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Erro", f"Erro ao recortar seleção: {e}")
        
    def paste_selection(self):
        """Cola a seleção mantendo posições relativas a partir de um ponto de origem"""
        try:
            if not hasattr(self, 'clipboard') or not self.clipboard:
                messagebox.showinfo("Info", "Área de transferência vazia")
                return
            
            # Verificar se clipboard tem estrutura nova (com 'elements' e 'origin')
            if isinstance(self.clipboard, dict) and 'elements' in self.clipboard:
                clipboard_elements = self.clipboard['elements']
                clipboard_origin = self.clipboard.get('origin', (0, 0))
            # Verificar se clipboard tem estrutura antiga (lista direta)
            elif isinstance(self.clipboard, list):
                clipboard_elements = self.clipboard
                # Calcular origem da estrutura antiga
                if clipboard_elements:
                    min_x = min(element.get('x', 0) for element in clipboard_elements)
                    min_y = min(element.get('y', 0) for element in clipboard_elements)
                    clipboard_origin = (min_x, min_y)
                else:
                    clipboard_origin = (0, 0)
            else:
                messagebox.showwarning("Aviso", "Formato de área de transferência não reconhecido")
                return

            # IGNORAR rails automáticos de estados antigos/seleção
            clipboard_elements = [e for e in clipboard_elements if not (e.get('type') == 'rail' and e.get('auto_rail'))]

            # Obter todas as posições selecionadas (células vazias E elementos existentes)
            selected_positions = []
            
            # Adicionar células vazias selecionadas
            empty_cells = [item for item in self.selected_elements if isinstance(item, tuple)]
            selected_positions.extend(empty_cells)
            
            # Adicionar posições de elementos selecionados
            selected_elements = [item for item in self.selected_elements if isinstance(item, dict)]
            for element in selected_elements:
                selected_positions.append((element.get('x'), element.get('y')))
            
            if not selected_positions:
                messagebox.showwarning("Aviso", "Selecione UMA célula ou elemento como ponto de origem para colar")
                return
            
            if len(selected_positions) > 1:
                messagebox.showwarning("Aviso", "Selecione apenas UMA célula como ponto de origem.\nOs elementos serão colados mantendo as posições relativas.")
                return
        
            # Ponto de origem para colagem
            origin_x, origin_y = selected_positions[0]
            
            # Usar origem do clipboard ou calcular dinamicamente
            min_x, min_y = clipboard_origin
            
            pasted_count = 0
                        
            for element in clipboard_elements:
                # Calcular posição relativa do elemento original
                element_x = element.get('x', 0)
                element_y = element.get('y', 0)
                
                # Calcular deslocamento relativo
                offset_x = element_x - min_x
                offset_y = element_y - min_y
                
                # Calcular nova posição baseada no ponto de origem
                new_x = origin_x + offset_x
                new_y = origin_y + offset_y
                                
                # Verificar se posição está ocupada - SEMPRE SUBSTITUIR
                if self.has_element_at_position(new_x, new_y):
                    existing_element = self.get_element_at_position(new_x, new_y)
                    if existing_element:
                        # snapshot pela remoção do existente
                        self.save_state_for_undo()
                        self.delete_element(existing_element)
                
                # Criar elemento na nova posição
                # snapshot por item colado
                self.save_state_for_undo()
                new_element = self._create_element_at_position(new_x, new_y, element)
                
                if new_element:
                    pasted_count += 1
                else:
                    print(f"FALHA ao colar {element.get('type')} em ({new_x}, {new_y})")
            
            # Limpar seleção e mostrar resultado
            self.clear_selection()
            
            if pasted_count > 0:
                messagebox.showinfo("Sucesso", f"{pasted_count} elemento(s) colado(s) mantendo posições relativas")
            else:
                messagebox.showwarning("Aviso", "Nenhum elemento pôde ser colado")

            self._mark_content_changed()
            
        except Exception as e:
            print(f"Erro ao colar: {e}")
            messagebox.showerror("Erro", f"Erro ao colar seleção: {e}")
    
    def _create_element_at_position(self, grid_x, grid_y, element_data):
        """Cria um elemento na posição especificada baseado nos dados fornecidos"""
        element_type = element_data.get('type')
        
        try:
            # Dispatch para função apropriada baseado no tipo
            if element_type == 'rail':
                new_element = self.add_rail_element(
                    grid_x, grid_y, 
                    element_data.get('angle', 0), 
                    element_data.get('mirror', 0)
                )
            elif element_type == 'sensor':
                new_element = self.add_sensor_element(
                    grid_x, grid_y, 
                    element_data.get('angle', 0)
                )
            elif element_type == 'switch':
                new_element = self.add_switch_element(
                    grid_x, grid_y, 
                    element_data.get('angle', 0), 
                    element_data.get('mirror', 0)
                )
            elif element_type == 'fma':
                # Determinar fma_type a partir dos dados salvos ou usar padrão baseado no ID
                fma_type = element_data.get('fma_type', 'FMA1')  # Usar fma_type salvo ou padrão
                if not fma_type:  # Se não tem fma_type definido, inferir pelo ID
                    element_id = element_data.get('id', '')
                    fma_type = 'FMA2' if str(element_id).startswith('4') else 'FMA1'
                
                new_element = self.add_fma_element(
                    grid_x, grid_y, 
                    element_data.get('angle', 0), 
                    element_data.get('name', f'FMA{self.next_fma_id}'),
                    fma_type
                )
            elif element_type == 'link':
                new_element = self.add_link_element(
                    grid_x, grid_y,
                    element_data.get('angle', 0),
                    element_data.get('url', ""),
                )
            elif element_type == 'crossing':
                new_element = self.add_crossing_element(
                    grid_x, grid_y,
                    element_data.get('angle', 0),
                )
            else:
                print(f"Tipo de elemento desconhecido: {element_type}")
                return None
            
            # Preservar propriedades específicas do elemento original
            if new_element and isinstance(new_element, dict):
                self._preserve_element_properties(new_element, element_data)
            
            return new_element
            
        except Exception as e:
            print(f"Erro ao criar elemento {element_type}: {e}")
            return None
    
    def _preserve_element_properties(self, new_element, original_data):
        """Preserva propriedades específicas do elemento original"""
        element_type = new_element.get('type')
        
        # Preservar nome para sensores e FMAs
        if 'name' in original_data and element_type in ['sensor', 'fma']:
            new_element['name'] = original_data['name']
            
            # Atualizar texto no canvas se houver text_id
            if 'text_id' in new_element:
                try:
                    self.trackplan_canvas.itemconfig(new_element['text_id'], text=original_data['name'])
                except:
                    pass  # Ignorar erros de canvas
        
        # Preservar ref_id
        if 'ref_id' in original_data:
            new_element['ref_id'] = original_data['ref_id']

        # Preservar url link
        if 'url' in original_data and element_type == 'link':
            new_element['url'] = original_data['url']

    def copy_debug_to_clipboard(self, content):
        """Copia conteúdo do debug para a área de transferência"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("Sucesso", "Debug copiado para a área de transferência")
        except Exception as e:
            print(f"Erro ao copiar debug: {e}")
    
    # === MÉTODOS PARA ELEMENTOS FDS ===
    
    def create_trackplan_designer_tab(self):
        """Cria a aba do designer de Trackplan minimalista com foco na grade"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Designer Trackplan")
        
        # === TOOLBAR COMPACTA NO TOPO ===
        toolbar = ttk.Frame(frame, padding="3")
        toolbar.pack(fill=tk.X)
        
        # Ferramentas principais (ícones apenas)
        tools_frame = ttk.Frame(toolbar)
        tools_frame.pack(side=tk.LEFT)
        
        self.tool_var = tk.StringVar(value="select")
        self.tool_buttons = {}
        
        # Botões de ferramenta minimalistas
        for text, value in [("Trilho", "rail"), ("Link", "link"), ("Chave", "switch"), ("Cruzamento", "crossing"), ("Sensor", "sensor"), 
                        ("FMA", "fma"), ("Selecionar", "select"), ("Borracha", "eraser")]:
            btn = ttk.Radiobutton(tools_frame, text=text, variable=self.tool_var, value=value,
                                 command=self.on_tool_change, width=10)
            btn.pack(side=tk.LEFT, padx=2)
            self.tool_buttons[value] = btn
        
        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, padx=8, fill=tk.Y)
        
        # Preview com imagem real (pequeno)
        preview_frame = ttk.Frame(toolbar)
        preview_frame.pack(side=tk.LEFT, padx=5)
        
        self.preview_canvas = tk.Canvas(preview_frame, width=30, height=30, bg="#f8f8f8", 
                                       relief="solid", borderwidth=1)
        self.preview_canvas.pack(side=tk.LEFT)
        
        # Controles compactos
        ttk.Label(toolbar, text="Ângulos:", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(10, 2))
        self.angle_var = tk.StringVar(value="0")
        self.angle_combo = ttk.Combobox(toolbar, textvariable=self.angle_var, 
                                       values=["0", "45", "90", "135", "180", "225", "270", "315"], 
                                       width=4, state="readonly", font=("Segoe UI", 8))
        self.angle_combo.pack(side=tk.LEFT, padx=1)
        self.angle_combo.bind("<<ComboboxSelected>>", lambda e: self.update_tool_preview())
        
        ttk.Label(toolbar, text="Mirror:", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(8, 2))
        self.mirror_var = tk.StringVar(value="0")
        self.mirror_combo = ttk.Combobox(toolbar, textvariable=self.mirror_var, 
                                        values=["0", "1"], width=2, state="readonly", font=("Segoe UI", 8))
        self.mirror_combo.pack(side=tk.LEFT, padx=1)
        self.mirror_combo.bind("<<ComboboxSelected>>", lambda e: self.update_tool_preview())
        
        ttk.Separator(toolbar, orient='vertical').pack(side=tk.LEFT, padx=8, fill=tk.Y)
        
        # Ações básicas
        ttk.Button(toolbar, text="↩ Desfazer", command=self.undo_action, width=10).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar, text="↪ Refazer", command=self.redo_action, width=10).pack(side=tk.LEFT, padx=(0,30))
        ttk.Button(toolbar, text="🧹 Limpar tudo", command=self.clear_trackplan, width=14).pack(side=tk.LEFT, padx=1)
        
        # Menu compacto para opções avançadas
        options_btn = ttk.Menubutton(toolbar, text="Configurações", width=13)
        options_btn.pack(side=tk.LEFT, padx=5)
        
        options_menu = tk.Menu(options_btn, tearoff=0)
        options_btn["menu"] = options_menu
        
        # Submenus organizados
        file_menu = tk.Menu(options_menu, tearoff=0)
        file_menu.add_command(label="Salvar Trackplan", command=self.save_trackplan)
        file_menu.add_command(label="Carregar Trackplan", command=self.load_trackplan)
        options_menu.add_cascade(label="📁 Arquivo", menu=file_menu)
        
        edit_menu = tk.Menu(options_menu, tearoff=0)
        edit_menu.add_command(label="Copiar", command=self.copy_selection)
        edit_menu.add_command(label="Recortar", command=self.cut_selection)
        edit_menu.add_command(label="Colar", command=self.paste_selection)
        edit_menu.add_separator()
        edit_menu.add_command(label="Editar FMA", command=self.open_fma_editor)
        edit_menu.add_command(label="Editar Sensor", command=self.open_sensor_editor)
        edit_menu.add_command(label="Editar Link", command=self.edit_link)
        edit_menu.add_separator()
        edit_menu.add_command(label="Finder",command=self.open_fma_test)
        options_menu.add_cascade(label="✏️ Edição", menu=edit_menu)
        
        options_menu.add_command(label="📐 Configurar Grade", command=self.show_grid_config)
        options_menu.add_command(label="Ajustar grade", command=self.fix_grid)
        options_menu.add_separator()
        options_menu.add_command(label="Trocar Modo FDS", command=self.change_fds_model)

        # Status info compacto no canto direito
        self.status_var = tk.StringVar(value="Trilho - 0° - Mirror: 0")
        status_label = ttk.Label(toolbar, textvariable=self.status_var, 
                                font=("Segoe UI", 8), foreground="#666")
        status_label.pack(side=tk.RIGHT, padx=10)
        
        # NOME DO FDS NO TOPO DO CANVAS
        fds_name_frame = ttk.Frame(frame, style="Section.TLabelframe")
        fds_name_frame.pack(fill=tk.X, padx=5, pady=(2, 0))
        
        # Configurar o grid do frame para expansão
        fds_name_frame.grid_columnconfigure(1, weight=1)

        # Variável para o nome do FDS
        self.trackplan_fds_name_var = tk.StringVar()

        # Label que mostra o nome do FDS
        self.fds_name_label = ttk.Label(fds_name_frame, 
                                    textvariable=self.trackplan_fds_name_var,
                                    font=("Segoe UI", 11, "bold"), 
                                    foreground="#1e3a5f",
                                    background="#f0f0f0",
                                    anchor="e")
        self.fds_name_label.grid(row=0, column=1, padx=5, pady=5, sticky="")

        # Atualizar nome inicial
        self.update_trackplan_fds_name()

        # === ÁREA DA GRADE (TELA CHEIA) ===
        canvas_frame = ttk.Frame(frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas principal ocupando toda a área restante
        self.trackplan_canvas = tk.Canvas(canvas_frame, bg="white", scrollregion=(0, 0, 2400, 800))
        
        # Scrollbars
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.trackplan_canvas.xview)
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.trackplan_canvas.yview)
        
        self.trackplan_canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
        
        # Layout em grade
        self.trackplan_canvas.grid(row=0, column=0, sticky="nsew")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        # === BARRA DE STATUS INFERIOR (minimalista) ===
        status_frame = ttk.Frame(frame)
        status_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.cell_info_var = tk.StringVar(value="")
        cell_label = ttk.Label(status_frame, textvariable=self.cell_info_var, 
                              font=("Segoe UI", 8), foreground="#888")
        cell_label.pack(side=tk.LEFT)
        
        self.selection_info_var = tk.StringVar(value="")
        selection_label = ttk.Label(status_frame, textvariable=self.selection_info_var, 
                                   font=("Segoe UI", 8), foreground="#0066cc")
        selection_label.pack(side=tk.LEFT, padx=20)
        
        # Atalhos de teclado (T/S/C/F/V/E/M) - info no canto direito
        shortcuts_label = ttk.Label(status_frame, 
                                   text="Atalhos: T-Trilho | L-Link | S-Sensor | C-Chave | F-FMA | V-Seleção | E-Borracha | M-Mirror | Ctrl+C-Copiar | Ctrl+X-Recortar | Ctrl+V-Colar | Ctrl+Z-Undo | Ctrl+Y-Redo | Del-Deletar | Ctrl+Shift+Clique-Área", 
                                   font=("Segoe UI", 7), foreground="#999")
        shortcuts_label.pack(side=tk.RIGHT)
        
        # === CONFIGURAR EVENTOS ===
        self.setup_trackplan_events()
        
        # === INICIALIZAR SISTEMA ===
        self.initialize_trackplan_system()
        
        # Variáveis adicionais para grade (ANTES de apply_grid)
        self.width_var = tk.StringVar(value="30")
        self.height_var = tk.StringVar(value="10")
        
        # ADICIONAR ESTAS LINHAS:
        self.form_fields["width_var"] = self.width_var
        self.form_fields["height_var"] = self.height_var

        # Forçar atualização da interface antes de aplicar a grade
        self.root.update_idletasks()
        
        # Aplicar grade e atualizar preview com delay
        self.root.after(100, self.apply_grid_delayed)
        self.update_tool_preview()
    
    def apply_grid_delayed(self):
        """Aplica grade com delay para garantir que o canvas esteja pronto"""
        try:
            self.apply_grid()
        except Exception as e:
            print(f"Erro ao aplicar grade com delay: {e}")
            # Tentar novamente após mais tempo
            print("Tentando aplicar grade novamente em 500ms...")
            self.root.after(500, self.apply_grid)
    
    # Método load_element_images removido - usar o método completo na linha ~6588
    
    def create_cubicles_tab(self):
        """Cria a aba de programação de cubículos"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Cubículos")
        
        # Layout principal
        main_paned = ttk.PanedWindow(frame, orient='horizontal')
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # === PAINEL ESQUERDO: LISTA DE CUBICLES ===
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        # Título e controles
        title_frame = ttk.Frame(left_frame)
        title_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(title_frame, text="Gerenciamento de Cubículos", font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
        
        # Botões de controle
        buttons_frame = ttk.Frame(left_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(buttons_frame, text="➕ Novo Cubículo", command=self.create_new_cubicle).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons_frame, text="Remover", command=self.remove_cubicles).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons_frame, text="Limpar Todos", command=self.clear_all_cubicles).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons_frame, text="Carregar do XML", command=self.load_cubicles_from_xml).pack(side=tk.LEFT, padx=4)

        # Lista de cubículos
        list_frame = ttk.LabelFrame(left_frame, text="Cubículos Existentes", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Treeview para cubículos
        columns = ("ID", "Nome", "Slots", "AEBs")
        self.cubicles_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)
        
        # Configurar colunas
        self.cubicles_tree.heading("ID", text="ID")
        self.cubicles_tree.heading("Nome", text="Nome")
        self.cubicles_tree.heading("Slots", text="Slots Totais")
        self.cubicles_tree.heading("AEBs", text="AEBs")
        
        self.cubicles_tree.column("ID", width=60, anchor="center")
        self.cubicles_tree.column("Nome", width=100, anchor="w")
        self.cubicles_tree.column("Slots", width=80, anchor="center")
        self.cubicles_tree.column("AEBs", width=60, anchor="center")
        
        # Scrollbar para a lista
        cubicles_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.cubicles_tree.yview)
        self.cubicles_tree.configure(yscrollcommand=cubicles_scrollbar.set)
        
        self.cubicles_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cubicles_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind para seleção
        self.cubicles_tree.bind("<<TreeviewSelect>>", self.on_cubicle_select)
        
        #Drag and Drop
        self.setup_cubicles_dnd()

        # === PAINEL DIREITO: EDITOR DE CUBICLE ===
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        
        # Título do editor
        editor_title = ttk.Label(right_frame, text="Editor de Cubículo", font=('Arial', 12, 'bold'))
        editor_title.pack(pady=5)
        
        # Notebook para o editor
        self.cubicle_editor_notebook = ttk.Notebook(right_frame)
        self.cubicle_editor_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Aba: Configurações Básicas
        self.create_cubicle_basic_tab()
        
        # Aba: Layout do Rack
        self.create_cubicle_rack_tab()
        
        # Aba: Validação e Exportação
        self.create_cubicle_exportation_tab()
        
        # Dados dos cubiculos
        self.cubicles_data = []
        self.current_cubicle = None
        
        # Carregar exemplo inicial
        self.load_sample_cubicles()
    
    def create_cubicle_basic_tab(self):
        """Cria a aba de configurações básicas do cubicle"""
        basic_frame = ttk.Frame(self.cubicle_editor_notebook)
        self.cubicle_editor_notebook.add(basic_frame, text="Básico")
        
        # Scrollable frame
        canvas = tk.Canvas(basic_frame)
        scrollbar = ttk.Scrollbar(basic_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Configurações do Cubicle
        cubicle_frame = ttk.LabelFrame(scrollable_frame, text="Informações do Cubículo", padding="10")
        cubicle_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # ID do Cubicle
        row = 0
        ttk.Label(cubicle_frame, text="ID do Cubículo:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.cubicle_id_var = tk.StringVar()
        ttk.Entry(cubicle_frame, textvariable=self.cubicle_id_var, width=15, state="readonly").grid(row=row, column=1, sticky="w", padx=10, pady=5)
        
        # Nome do Cubículo
        row += 1
        ttk.Label(cubicle_frame, text="Nome do Cubículo:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.cubicle_name_var = tk.StringVar()
        ttk.Entry(cubicle_frame, textvariable=self.cubicle_name_var, width=30).grid(row=row, column=1, sticky="w", padx=10, pady=5)
        
        # Altura
        row += 1
        ttk.Label(cubicle_frame, text="Altura:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.cubicle_height_var = tk.StringVar(value="1")
        ttk.Entry(cubicle_frame, textvariable=self.cubicle_height_var, width=10).grid(row=row, column=1, sticky="w", padx=10, pady=5)
        
        # Configurações do Rack
        rack_frame = ttk.LabelFrame(scrollable_frame, text="Configurações do Rack", padding="10")
        rack_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # ID do Rack
        row = 0
        ttk.Label(rack_frame, text="ID do Rack:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.rack_id_var = tk.StringVar()
        ttk.Entry(rack_frame, textvariable=self.rack_id_var, width=15, state="readonly").grid(row=row, column=1, sticky="w", padx=10, pady=5)

        # Configurações do Backplane
        bp_frame = ttk.LabelFrame(scrollable_frame, text="Configurações do Backplane", padding="10")
        bp_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # ID do Backplane
        row = 0
        ttk.Label(bp_frame, text="ID do Backplane:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.bp_id_var = tk.StringVar()
        ttk.Entry(bp_frame, textvariable=self.bp_id_var, width=15, state='readonly').grid(row=row, column=1, sticky="w", padx=10, pady=5)
        
        # Tamanho do Backplane
        row += 1
        ttk.Label(bp_frame, text="Tamanho (slots):", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.bp_size_var = tk.StringVar(value="13")
        bp_size_entry = ttk.Entry(bp_frame, textvariable=self.bp_size_var, width=10)
        bp_size_entry.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        bp_size_entry.bind("<KeyRelease>", self.on_bp_size_change)
        bp_size_entry.bind("<FocusOut>", self.on_bp_size_change)
        
        # Adicionar label de ajuda
        ttk.Label(bp_frame, text="(min: 1, max: 50)", font=("Arial", 8), foreground="gray").grid(row=row, column=2, sticky="w", padx=5)
        
        # Slot Inicial
        row += 1
        ttk.Label(bp_frame, text="Slot Inicial:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.bp_start_slot_var = tk.StringVar(value="1")
        ttk.Entry(bp_frame, textvariable=self.bp_start_slot_var, width=10, state="readonly").grid(row=row, column=1, sticky="w", padx=10, pady=5)
        
        # Botões de ação
        action_frame = ttk.Frame(scrollable_frame)
        action_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(action_frame, text="Salvar Configurações", command=self.save_cubicle_basic_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Atualizar Layout", command=self.update_rack_layout).pack(side=tk.LEFT, padx=5)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_cubicle_rack_tab(self):
        """Cria a aba de layout do rack"""
        rack_frame = ttk.Frame(self.cubicle_editor_notebook)
        self.cubicle_editor_notebook.add(rack_frame, text="Layout do Rack")
        
        # Controles superiores
        controls_frame = ttk.Frame(rack_frame)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(controls_frame, text="Layout Visual do Rack", font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
        
        # Botões de controle
        ttk.Button(controls_frame, text="Limpar Tudo", command=self.clear_rack).pack(side=tk.RIGHT, padx=5)
        
        # Frame principal do rack
        main_rack_frame = ttk.Frame(rack_frame)
        main_rack_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Frame para o visual do rack
        visual_frame = ttk.LabelFrame(main_rack_frame, text="Visual do Rack", padding="10")
        visual_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Container para canvas e scrollbars
        canvas_container = ttk.Frame(visual_frame)
        canvas_container.pack(fill=tk.BOTH, expand=True)
        
        # Canvas para desenhar o rack com scroll configurado
        self.rack_canvas = tk.Canvas(canvas_container, bg="lightgray", width=600, height=400,
                                    scrollregion=(0, 0, 1200, 400))  # Região de scroll expandida

        self.rack_canvas.create_text(300, 200, text="Nenhum cubículo selecionado", font=("Arial", 12), fill="gray")

        # Scrollbar horizontal
        h_scrollbar = ttk.Scrollbar(canvas_container, orient="horizontal", command=self.rack_canvas.xview)
        self.rack_canvas.configure(xscrollcommand=h_scrollbar.set)
        
        # Layout em grade para canvas e scrollbar
        self.rack_canvas.grid(row=0, column=0, sticky="nsew")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Configurar expansão
        canvas_container.grid_rowconfigure(0, weight=1)
        canvas_container.grid_columnconfigure(0, weight=1)
    
        # Frame de propriedades do slot selecionado
        properties_frame = ttk.LabelFrame(main_rack_frame, text="Propriedades do Slot", padding="10")
        properties_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        # Slot selecionado
        ttk.Label(properties_frame, text="Slot Selecionado:", font=("Arial", 9, "bold")).grid(row=0, column=0, sticky="w", pady=5)
        self.selected_slot_var = tk.StringVar(value="Nenhum")
        ttk.Label(properties_frame, textvariable=self.selected_slot_var, foreground="blue").grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Tipo do componente
        row = 1
        ttk.Label(properties_frame, text="Tipo:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.slot_type_var = tk.StringVar()
        type_combo = ttk.Combobox(properties_frame, textvariable=self.slot_type_var, 
                                 values=["EmptySlot","Com", "Aeb", "Aeb+IoExb"], width=15, state="readonly")
        type_combo.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        type_combo.bind("<<ComboboxSelected>>", self.on_slot_type_change)

        self.slot_type_combo = type_combo  # Guardar referência para uso posterior
        # ID do componente
        row += 1
        ttk.Label(properties_frame, text="ID:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.slot_id_var = tk.StringVar()
        id_entry = ttk.Entry(properties_frame, textvariable=self.slot_id_var, width=15)
        id_entry.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        id_entry.bind('<FocusOut>', self.on_slot_id_change)

        # Guarda a referência para controlar o cursor
        self.slot_id_entry = id_entry

        # Disparar salvar ao pressionar Enter (inclui Enter do teclado numérico)
        self.slot_id_entry.bind('<Return>', lambda e: self.apply_slot_changes())
        self.slot_id_entry.bind('<KP_Enter>', lambda e: self.apply_slot_changes())

        # Forçar prefixo de ID conforme tipo (Aeb=1..., IoExb=5..., Com=0)
        self.slot_id_var.trace_add('write', self._enforce_slot_id_prefix_trace)

        # Campos automáticos (read-only) que aparecem conforme o tipo
        # Nome do componente
        row += 1
        self.name_label = ttk.Label(properties_frame, text="Nome:", font=("Arial", 9, "bold"))
        self.slot_name_var = tk.StringVar()
        self.name_entry = ttk.Entry(properties_frame, textvariable=self.slot_name_var, width=15, state="readonly")
        
        # CAN ID (para Com e Aeb)
        row += 1
        self.can_id_label = ttk.Label(properties_frame, text="CAN ID:", font=("Arial", 9, "bold"))
        self.slot_can_id_var = tk.StringVar()
        self.can_id_entry = ttk.Entry(properties_frame, textvariable=self.slot_can_id_var, width=15, state="readonly")
        
        # Ref ID (para Aeb e IoExb)
        row += 1
        self.ref_id_label = ttk.Label(properties_frame, text="Ref ID:", font=("Arial", 9, "bold"))
        self.slot_ref_id_var = tk.StringVar()
        self.ref_id_entry = ttk.Entry(properties_frame, textvariable=self.slot_ref_id_var, width=15, state="readonly")
        
        # Info sobre campos automáticos
        row += 1
        info_label = ttk.Label(properties_frame, text="📝 Os campos Nome, CAN ID e Ref ID\nsão preenchidos automaticamente\nbaseados no ID inserido.", 
                              font=("Arial", 8), foreground="gray")
        info_label.grid(row=row, column=0, columnspan=2, pady=10)
        
        # Botões de ação
        row += 2
        ttk.Button(properties_frame, text="Aplicar", command=self.apply_slot_changes).grid(row=row, column=0, pady=10)
        ttk.Button(properties_frame, text="Limpar Slot", command=self.clear_selected_slot).grid(row=row, column=1, padx=5, pady=10)
        
        # Vincular clique no canvas
        self.rack_canvas.bind("<Button-1>", self.on_rack_canvas_click)
        
        # Bind por tag: mais preciso que find_closest e respeita o scroll
        self.rack_canvas.tag_bind("slot", "<Button-1>", self.on_rack_slot_click)

        # Configurar navegação por teclado
        self.setup_rack_keyboard_navigation()

        # Dados do rack
        self.rack_slots = {}
        self.selected_slot = None
    
    def create_cubicle_exportation_tab(self):
        """Cria a aba de Exportação"""
        # Frame da aba no notebook
        tab_frame = ttk.Frame(self.cubicle_editor_notebook)
        self.cubicle_editor_notebook.add(tab_frame, text="Validação")

        # Container rolável (canvas + scrollbar vertical)
        canvas = tk.Canvas(tab_frame, highlightthickness=0, bg=self.root.cget("bg"))
        v_scrollbar = ttk.Scrollbar(tab_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Título
        ttk.Label(scrollable, text="Validação e Exportação", font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Botões de ação
        actions_frame = ttk.Frame(scrollable)
        actions_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(actions_frame, text="Validar Cubículo", command=self.validate_cubicle).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Validar Todos", command=self.validate_all_cubicles).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Gerar XML", command=lambda: self.generate_cubicle_xml(self.fds_model)).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="XML de Todos Cubículos", command=self.generate_all_cubicles_xml).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Salvar XML", command=self.save_cubicle_xml).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions_frame, text="Exportar do FdsConfig", command=self.apply_fdsconfig_to_cubicles).pack(side=tk.LEFT, padx=5)

        # Resultado da validação
        validation_frame = ttk.LabelFrame(scrollable, text="Resultado da Validação", padding="10")
        validation_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=5)

        self.validation_output_text = tk.Text(validation_frame, height=10, wrap=tk.WORD)
        validation_v_scrollbar = ttk.Scrollbar(validation_frame, orient="vertical", command=self.validation_output_text.yview)
        self.validation_output_text.configure(yscrollcommand=validation_v_scrollbar.set)

        self.validation_output_text.grid(row=0, column=0, sticky="nsew")
        validation_v_scrollbar.grid(row=0, column=1, sticky="ns")
        validation_frame.grid_rowconfigure(0, weight=1)
        validation_frame.grid_columnconfigure(0, weight=1)

        # Preview do XML
        preview_frame = ttk.LabelFrame(scrollable, text="Preview do XML", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.xml_preview_text = tk.Text(preview_frame, height=30, wrap=tk.NONE)
        xml_h_scrollbar = ttk.Scrollbar(preview_frame, orient="horizontal", command=self.xml_preview_text.xview)
        xml_v_scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self.xml_preview_text.yview)
        self.xml_preview_text.configure(xscrollcommand=xml_h_scrollbar.set, yscrollcommand=xml_v_scrollbar.set)
        
        self.xml_preview_text.grid(row=0, column=0, sticky="nsew")
        xml_v_scrollbar.grid(row=0, column=1, sticky="ns")
        xml_h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        preview_frame.grid_rowconfigure(0, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)
    
    # === MÉTODOS PARA CUBICLES ===
    
    def create_new_cubicle(self):
        """Cria um novo cubicle"""
        new_id = str(9000 + (len(self.cubicles_data) + 1))
        new_name = f"CUBICLE-{len(self.cubicles_data) + 1}"
        
        # Calcular próximo ID do rack (incremento de 100)
        idx = len(self.cubicles_data)
        next_rack_base = (8000 + 100*idx + (72000 if idx > 9 else 0)) + 1

        cubicle = {
            'id': new_id,
            'name': new_name,
            'height': '1',
            'rack': {
                'id': str(next_rack_base),
                'bp': {
                    'id': str(next_rack_base + 1),
                    'size': '13',
                    'startSlot': '1',
                    'slots': {},
                }
            }
        }
        
        # Inicializar slots vazios
        for i in range(1, 14):  # 13 slots por padrão
            cubicle['rack']['bp']['slots'][str(i)] = {
                'id': f"{next_rack_base + i + 1}",
                'type': 'EmptySlot',
                'slotId': str(i)
            }
        
        # Sempre colocar PSC no slot 1
        cubicle['rack']['bp']['slots']['1'] = {
            'id': str(next_rack_base + 2),
            'type': 'Psc',
            'slotId': '1'
        }
        
        self.cubicles_data.append(cubicle)
        self.update_cubicles_list()
        
        # Selecionar o novo cubicle
        item_id = self.cubicles_tree.get_children()[-1]
        self.cubicles_tree.selection_set(item_id)
        self.on_cubicle_select()
        self.refresh_cub_list()

    def remove_cubicles(self):
        """Remove o cubicle selecionado"""
        selection = self.cubicles_tree.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um cubicle para remover.")
            return
        
        if messagebox.askyesno("Confirmar", "Tem certeza que deseja remover estes cubicles?"):
            for idx, items in enumerate(selection):
                item_id = selection[idx]
                index = self.cubicles_tree.index(item_id)
                del self.cubicles_data[index]
                self.update_cubicles_list()

        self.renumber_cubicles_by_position()
        self.renumber_psc_and_empty()
        self.current_cubicle = None
        self.clear_cubicle_editor()
        self.update_cubicles_list()
        self.refresh_cub_list()

    
    def clear_all_cubicles(self):
        """Remove todos os cubicles da lista"""
        if not hasattr(self, 'cubicles_data') or not self.cubicles_data:
            messagebox.showinfo("Aviso", "Não há cubículos para remover!")
            return
        
        # Confirmar ação
        total_cubicles = len(self.cubicles_data)
        response = messagebox.askyesno(
            "Confirmar Limpeza", 
            f"Deseja realmente remover todos os {total_cubicles} cubículos?\n\n"
            "Esta ação não pode ser desfeita!"
        )
        
        if response:
            try:
                # Limpar todos os cubicles
                self.cubicles_data.clear()
                self.update_cubicles_list()
                self.current_cubicle = None
                self.clear_cubicle_editor()
                
                messagebox.showinfo("Sucesso", 
                    f"Todos os {total_cubicles} cubículos foram removidos com sucesso!")
                
            except Exception as e:
                print(f"Erro ao limpar cubicles: {e}")
                messagebox.showerror("Erro", f"Erro ao remover cubículo: {e}")
    
    def _enforce_slot_id_prefix_trace(self, *args):
        """Callback de trace para aplicar prefixo do ID conforme o tipo do slot."""
        try:
            self.enforce_slot_id_prefix()
        except Exception:
            pass

    def enforce_slot_id_prefix(self):
        """Garante prefixo do ID conforme o tipo do slot:
           - Aeb  -> começa com '1'
           - IoExb-> começa com '5'
           - Com -> começa com '0'
           Não afeta EmptySlot/Psc."""
        try:
            if not hasattr(self, 'slot_type_var') or not hasattr(self, 'slot_id_var'):
                return
            slot_type = self.slot_type_var.get()
            if slot_type not in ('Aeb', 'IoExb','Com'):
                return

            # Evitar recursão ao setar a StringVar
            if getattr(self, '_enforcing_slot_id', False):
                return
            self._enforcing_slot_id = True

            current = (self.slot_id_var.get() or "").strip()
            if slot_type == 'Aeb':
                prefix = '1'
            elif slot_type == 'IoExb':
                prefix = '5'
            else:
                prefix = '0'

            def _set_and_put_caret(val: str):
                # seta o valor e move o cursor para o fim no próximo ciclo do loop do Tk
                self.slot_id_var.set(val)
                if hasattr(self, 'slot_id_entry') and self.slot_id_entry:
                    self.root.after(0, lambda: self.slot_id_entry.icursor(tk.END))

            if not current:
                _set_and_put_caret(prefix)
                return

            # Se o primeiro caractere não for dígito, apenas força o prefixo
            if not current[0].isdigit():
                _set_and_put_caret(prefix + current)
                return

            # Se já começa com o prefixo correto, não faz nada além de garantir caret no fim
            if current.startswith(prefix):
                # não altere o texto do usuário; apenas garanta o caret no fim quando o prefixo foi injetado antes
                # (chamar after para não atrapalhar a digitação)
                if hasattr(self, 'slot_id_entry') and self.slot_id_entry:
                    self.root.after(0, lambda: self.slot_id_entry.icursor(tk.END))
                return

            # Troca apenas o primeiro dígito pelo prefixo correto
            new_value = prefix + current[1:]
            _set_and_put_caret(new_value)
        finally:
            self._enforcing_slot_id = False

    def load_cubicles_from_xml(self, filename=None):
        """Carrega cubicles de um arquivo Trackplan.xml"""
        if filename is None:
            filename = filedialog.askopenfilename(
                title="Carregar Trackplan.xml",
                defaultextension=".xml",
                filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
            )

        if not filename:
            return

        try:
            # String de caminho
            if isinstance(filename, str):
                tree = ET.parse(filename)

            # Bytes (conteúdo vindo do zip)
            elif isinstance(filename, bytes):
                tree = ET.ElementTree(ET.fromstring(filename))

            # File-like object
            else:
                tree = ET.parse(filename)

            root = tree.getroot()

            # Procurar seção de Cubicles
            if root.tag == 'Cubicles':
                cubicles_section = root
            elif root.tag == 'Trackplan':
                cubicles_section = root.find("Cubicles")
            else:
                cubicles_section = root.find('.//Cubicles')

            if cubicles_section is None:
                messagebox.showwarning("Aviso", "Arquivo XML não contém seção de Cubículos.")
                return
            
            self.cubicles_data.clear()
            for cubicle_elem in cubicles_section.findall("Cubicle"):
                cubicle_data = self.parse_cubicle_from_xml(cubicle_elem)
                if cubicle_data:
                    self.cubicles_data.append(cubicle_data)

            # IDs fixos por posição
            self.renumber_cubicles_by_position()

            self.update_cubicles_list()
            self.refresh_cub_list()
            self.cubicles_file_path = filename  # necessário para persistência no mesmo XML

            messagebox.showinfo("Sucesso", f"Carregados {len(self.cubicles_data)} cubículos do arquivo XML.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar XML: {str(e)}")

    def parse_cubicle_from_xml(self, cubicle_elem):
        """Converte elemento XML de cubicle para estrutura de dados"""
        try:
            cubicle = {
                'id': cubicle_elem.get('id', ''),
                'name': cubicle_elem.get('name', ''),
                'height': cubicle_elem.get('height', '1'),
                'rack': {}
            }
            
            # Processar Rack
            rack_elem = cubicle_elem.find("Rack")
            if rack_elem is not None:
                cubicle['rack']['id'] = rack_elem.get('id', '')
                
                # Processar Backplane
                bp_elem = rack_elem.find("Bp")
                if bp_elem is not None:
                    cubicle['rack']['bp'] = {
                        'id': bp_elem.get('id', ''),
                        'size': bp_elem.get('size', '13'),
                        'startSlot': bp_elem.get('startSlot', '1'),
                        'slots': {}
                    }
                    
                    # Processar slots
                    slot_types = ['Psc', 'Com', 'Aeb', 'IoExb', 'EmptySlot']
                    for slot_type in slot_types:
                        for slot_elem in bp_elem.findall(slot_type):
                            slot_id = slot_elem.get('slotId', '')
                            if slot_id:
                                slot_data = {
                                    'id': slot_elem.get('id', ''),
                                    'type': slot_type,
                                    'slotId': slot_id
                                }
                                
                                # Adicionar atributos específicos do tipo
                                if slot_type == 'Com':
                                    slot_data['canId'] = slot_elem.get('canId', '')
                                    slot_data['type_com'] = slot_elem.get('type', '')
                                    slot_data['redundant'] = slot_elem.get('redundant', '')
                                    slot_data['name'] = slot_elem.get('name', '')
                                elif slot_type == 'Aeb':
                                    slot_data['name'] = slot_elem.get('name', '')
                                    slot_data['canId'] = slot_elem.get('canId', '')
                                    slot_data['refId'] = slot_elem.get('refId', '')
                                elif slot_type == 'IoExb':
                                    slot_data['name'] = slot_elem.get('name', '')
                                    slot_data['refId'] = slot_elem.get('refId', '')
                                    slot_data['fma0RefId'] = slot_elem.get('fma0RefId', '')
                                    slot_data['fma1RefId'] = slot_elem.get('fma1RefId', '')
                                
                                cubicle['rack']['bp']['slots'][slot_id] = slot_data
            
            return cubicle
            
        except Exception as e:
            print(f"Erro ao processar cubicle: {e}")
            return None
    
    def update_cubicles_list(self):
        """Atualiza a lista de cubicles"""
        # Limpar lista
        for item in self.cubicles_tree.get_children():
            self.cubicles_tree.delete(item)
        
        # Adicionar cubicles
        for cubicle in self.cubicles_data:
            # Contar AEBs
            aeb_count = 0
            slots = cubicle.get('rack', {}).get('bp', {}).get('slots', {})
            for slot in slots.values():
                if slot.get('type') == 'Aeb':
                    aeb_count += 1
            
            # Status baseado na completude
            total_slots = int(cubicle.get('rack', {}).get('bp', {}).get('size', '0'))
            empty_slots = sum(1 for slot in slots.values() if slot.get('type') == 'EmptySlot')
            
            if empty_slots == total_slots - 1:  # -1 para o PSC
                status = "Vazio"
            elif empty_slots > 0:
                status = "Parcial"
            else:
                status = "Completo"
            
            # iid estável = id do cubicle
            self.cubicles_tree.insert(
                "", "end",
                iid=str(cubicle.get('id', '')),  # chave estável
                values=(
                    cubicle.get('id', ''),
                    cubicle.get('name', ''),
                    total_slots,
                    aeb_count,
                    status
                )
            )
            
    def renumber_psc_and_empty(self):
        """Renumera IDs do PSC e EmptySlots de todos os cubículos após remoção"""
        try:            
            renumbered_count = 0
            
            for cubicle_index, cubicle in enumerate(self.cubicles_data):
                try:
                    # Obter rack do cubículo
                    rack = cubicle.get('rack', {})
                    rack_id = rack.get('id', '')
                    
                    if not rack_id:
                        continue
                    
                    # Calcular nova base para IDs baseada no rack_id
                    try:
                        base_id = int(rack_id)
                    except ValueError:
                        continue
                    
                    # Obter backplane
                    bp = rack.get('bp', {})
                    slots = bp.get('slots', {})
                    
                    if not slots:
                        print(f"Cubículo {cubicle_index + 1} sem slots")
                        continue
                    
                    # Renumerar slots específicos
                    slots_updated = 0
                    
                    for slot_id, slot in slots.items():
                        slot_type = slot.get('type', 'EmptySlot')
                        
                        # Renumerar apenas PSC e EmptySlots
                        if slot_type in ['Psc', 'EmptySlot']:
                            try:
                                slot_number = int(slot_id)
                                # Calcular novo ID: base + slot_number + 1
                                new_slot_id = str(base_id + slot_number + 1)
                                
                                # Verificar se o ID mudou
                                old_id = slot.get('id', '')
                                if old_id != new_slot_id:
                                    slot['id'] = new_slot_id
                                    slots_updated += 1                                
                            except ValueError:
                                continue
                    
                    if slots_updated > 0:
                        renumbered_count += slots_updated
                    
                except Exception as e:
                    continue

            return renumbered_count
        except Exception as e:
            return 0

    def on_cubicle_select(self, event=None):
        """Chamado quando um cubicle é selecionado"""
        selection = self.cubicles_tree.selection()
        if not selection:
            return
        
        item_id = selection[0]
        index = self.cubicles_tree.index(item_id)
        self.current_cubicle = self.cubicles_data[index]
        
        # Carregar dados no editor
        self.load_cubicle_in_editor()

    def load_cubicle_in_editor(self):
        """Carrega os dados do cubicle atual no editor"""
        if not self.current_cubicle:
            return
        
        # Aba básica
        self.cubicle_id_var.set(self.current_cubicle.get('id', ''))
        self.cubicle_name_var.set(self.current_cubicle.get('name', ''))
        self.cubicle_height_var.set(self.current_cubicle.get('height', '1'))
        
        rack = self.current_cubicle.get('rack', {})
        self.rack_id_var.set(rack.get('id', ''))
        
        bp = rack.get('bp', {})
        self.bp_id_var.set(bp.get('id', ''))
        self.bp_size_var.set(bp.get('size', '13'))
        self.bp_start_slot_var.set(bp.get('startSlot', '1'))
        
        # Carregar slots no layout do rack
        self.rack_slots = bp.get('slots', {}).copy()
        self.draw_rack_layout()
    
    def clear_cubicle_editor(self):
        """Limpa o editor de cubicle"""
        self.cubicle_id_var.set('')
        self.cubicle_name_var.set('')
        self.cubicle_height_var.set('1')
        self.rack_id_var.set('')
        self.bp_id_var.set('')
        self.bp_size_var.set('13')
        self.bp_start_slot_var.set('1')
        self.rack_slots.clear()
        self.selected_slot = None
        self.selected_slot_var.set('Nenhum')
        self.draw_rack_layout()
    
    def setup_cubicles_dnd(self):
        """Configura DnD (arrastar para reordenar) na lista de cubículos."""
        self._cub_dnd = {
            'dragging': False,
            'drag_iid': None,
            'start_index': None
        }
        tree = self.cubicles_tree
        tree.bind('<ButtonPress-1>', self._cub_on_press)
        tree.bind('<B1-Motion>', self._cub_on_motion)
        tree.bind('<ButtonRelease-1>', self._cub_on_release)

    def _cub_on_press(self, event):
        """Inicia o arraste se clicou em uma linha válida."""
        tree = self.cubicles_tree
        iid = tree.identify_row(event.y)
        if not iid:
            return
        # Seleciona a linha clicada e registra estado inicial
        tree.selection_set(iid)
        self._cub_dnd['dragging'] = True
        self._cub_dnd['drag_iid'] = iid
        self._cub_dnd['start_index'] = tree.index(iid)

    def _cub_on_motion(self, event):
        """Move visualmente o item durante o arraste."""
        if not self._cub_dnd.get('dragging'):
            return
        tree = self.cubicles_tree
        src_iid = self._cub_dnd.get('drag_iid')
        if not src_iid:
            return

        # Descobrir destino pela posição do mouse
        dest_iid = tree.identify_row(event.y)
        children = tree.get_children()
        if not children:
            return

        if dest_iid:
            dst_index = tree.index(dest_iid)
        else:
            # Fora das linhas: snap para final/início conforme y
            if event.y < 0:
                dst_index = 0
            else:
                dst_index = len(children) - 1

        # Se destino mudou, mover item visualmente
        if tree.index(src_iid) != dst_index:
            tree.move(src_iid, '', dst_index)

    def _cub_on_release(self, event):
        """Finaliza arraste, sincroniza modelo e atualiza UI."""
        if not self._cub_dnd.get('dragging'):
            return
        tree = self.cubicles_tree

        try:
            src_index = self._cub_dnd.get('start_index')
            drag_iid = self._cub_dnd.get('drag_iid')
            if drag_iid is None or src_index is None:
                return

            # Ordem final visível
            ordered_iids = list(tree.get_children())
            new_index = ordered_iids.index(drag_iid)

            self._cub_dnd['dragging'] = False
            self._cub_dnd['drag_iid'] = None
            self._cub_dnd['start_index'] = None

            # Nada mudou
            if new_index == src_index:
                return

            # Reconstruir self.cubicles_data segundo a ordem visual
            by_id = {str(c.get('id', '')): c for c in self.cubicles_data}
            new_data = []
            for iid in ordered_iids:
                c = by_id.get(str(iid))
                if c is not None:
                    new_data.append(c)
            # Garantir que nada ficou de fora (caso haja itens sem iid)
            if len(new_data) == len(self.cubicles_data):
                self.cubicles_data = new_data

            # RENOMEAR IDs pela posição
            self.renumber_cubicles_by_position()

            #Renumerar PSC e EmptySlots
            self.renumber_psc_and_empty()

            # Recriar lista e restaurar seleção
            self.update_cubicles_list()
            new_iid = str(9001 + new_index)
            if drag_iid in self.cubicles_tree.get_children():
                tree.selection_set(new_iid)
                self.on_cubicle_select()

            #Salvar ordem
            self.persist_cubicles_order()
        finally:    
            # Garantir reset do estado
            self._cub_dnd['dragging'] = False
            self._cub_dnd['drag_iid'] = None
            self._cub_dnd['start_index'] = None
            self.refresh_cub_list()

    def _sync_and_refresh_cubicles_list(self):
        """Sincroniza o editor com o modelo e atualiza a lista de cubículos."""
        try:
            self._sync_current_cubicle_from_editor()
            self.update_cubicles_list()
        except Exception as e:
            print(f"Erro ao sincronizar cubículos: {e}")

    def on_bp_size_change(self, event=None):
        """Chamado quando o tamanho do backplane muda"""
        if not self.current_cubicle:
            return

        # Validar entrada
        size_text = self.bp_size_var.get().strip()
        if not size_text:
            return  # Campo vazio, não fazer nada
        
        try:
            new_size = int(size_text)
            
            # Validar limites
            if new_size < 1:
                messagebox.showwarning("Valor Inválido", "O tamanho mínimo é 1 slot.")
                self.bp_size_var.set("1")
                new_size = 1
            elif new_size > 50:
                messagebox.showwarning("Valor Inválido", "O tamanho máximo é 50 slots.")
                self.bp_size_var.set("50")
                new_size = 50
                
        except ValueError:
            # Valor não é um número válido
            messagebox.showwarning("Valor Inválido", "Digite apenas números inteiros.")
            self.bp_size_var.set("13")  # Valor padrão
            new_size = 13
        
        # Calcular base para IDs baseado no rack
        rack_id = self.rack_id_var.get()
        if rack_id.isdigit():
            base_id = int(rack_id)
        else:
            base_id = 8001
        
        # Ajustar slots
        current_slots = self.rack_slots.copy()
        self.rack_slots.clear()
        
        for i in range(1, new_size + 1):
            slot_id = str(i)
            if slot_id in current_slots:
                # Manter slot existente
                self.rack_slots[slot_id] = current_slots[slot_id]
            else:
                # Criar novo slot vazio
                self.rack_slots[slot_id] = {
                    'id': f"{base_id + i + 1}",
                    'type': 'EmptySlot',
                    'slotId': slot_id
                }
        
        # Garantir PSC no slot 1
        if '1' in self.rack_slots:
            if self.rack_slots['1']['type'] != 'Psc':
                self.rack_slots['1']['type'] = 'Psc'
                self.rack_slots['1']['id'] = f"{base_id + 2:05d}"

        self.draw_rack_layout()
        # >>> sincronizar e atualizar lista
        self._sync_and_refresh_cubicles_list()

    def scroll_rack_home(self, event):
        """Vai para o início do rack"""
        self.rack_canvas.xview_moveto(0)

    def scroll_rack_end(self, event):
        """Vai para o final do rack"""
        self.rack_canvas.xview_moveto(1)

    def on_rack_mouse_wheel(self, event):
        """Controla scroll horizontal com wheel do mouse"""
        # Scroll horizontal com wheel
        self.rack_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def draw_rack_layout(self):
        """Desenha o layout visual do rack com scroll automático"""
        self.rack_canvas.delete("all")
        
        if not self.rack_slots:
            self.rack_canvas.create_text(300, 200, text="Nenhum cubículo selecionado", font=("Arial", 12), fill="gray")
            return
        
        # Configurações de desenho
        slot_width = 40
        slot_height = 60
        margin = 20
        spacing = 5
        
        # Cores por tipo
        colors = {
            'Psc': '#FFD700',      # Dourado para PSC
            'Com': '#90EE90',      # Verde claro para COM
            'Aeb': "#60A6C2",      # Azul claro para AEB
            'IoExb': "#A3B0E7",    # Roxo claro para IoExb
            'EmptySlot': "#413F3F" # Cinza claro para vazio
        }
        
        # Calcular posições e atualizar scroll region
        total_slots = len(self.rack_slots)
        total_width = total_slots * (slot_width + spacing) + (2 * margin)
        
        # Atualizar região de scroll dinamicamente
        self.rack_canvas.configure(scrollregion=(0, 0, total_width, 400))
        
        start_x = margin
        
        # Desenhar título
        title_x = max(300, total_width // 2)  # Centralizar ou usar posição mínima
        self.rack_canvas.create_text(title_x, 30, text=f"Rack: {self.current_cubicle.get('name', 'N/A')}", 
                                    font=("Arial", 12, "bold"))
        
        # Informação sobre número de slots
        info_text = f"Total de Slots: {total_slots}"
        if total_slots > 13:
            info_text += " (Use a barra de rolagem para navegar)"
        self.rack_canvas.create_text(title_x, 50, text=info_text, 
                                    font=("Arial", 9), fill="gray")
        
        # Desenhar slots
        y = 80
        for i in range(1, total_slots + 1):
            slot_id = str(i)
            x = start_x + (i - 1) * (slot_width + spacing)
            
            if slot_id in self.rack_slots:
                slot = self.rack_slots[slot_id]
                slot_type = slot.get('type', 'EmptySlot')
                color = colors.get(slot_type, '#F0F0F0')
                
                # Desenhar retângulo do slot (tags: 'slot' + específico)
                rect_id = self.rack_canvas.create_rectangle(
                    x, y, x + slot_width, y + slot_height,
                    fill=color, outline="black", width=2,
                    tags=("slot", f"slot_{slot_id}")
                )
                
                # Destacar se selecionado
                if self.selected_slot == slot_id:
                    self.rack_canvas.create_rectangle(
                        x-2, y-2, x + slot_width + 2, y + slot_height + 2,
                        outline="deepskyblue", width=2, dash=(4,2),
                        tags=("slot_sel", f"slot_{slot_id}")
                    )
                
                # Texto do slot
                self.rack_canvas.create_text(
                    x + slot_width // 2, y + 10,
                    text=f"Slot {slot_id}", font=("Arial", 8, "bold"),
                    tags=("slot", f"slot_{slot_id}")
                )
                
                if slot_type != 'EmptySlot':
                    # ID ou nome
                    name = slot.get('name', slot.get('id', ''))
                    if name:
                        self.rack_canvas.create_text(
                            x + slot_width // 2, y + 40,
                            text=name, font=("Arial", 6),
                            tags=("slot", f"slot_{slot_id}")
                        )
        
        # Legenda (posicionada dinamicamente)
        legend_y = y + slot_height + 30
        legend_items = [
            ('PSC', colors['Psc']),
            ('COM', colors['Com']),
            ('AEB', colors['Aeb']),
            ('IoExb', colors['IoExb']),
            ('Vazio', colors['EmptySlot'])
        ]
        
        legend_start_x = max(50, (total_width - 400) // 2)  # Centralizar legenda
        legend_x = legend_start_x
        for item, color in legend_items:
            self.rack_canvas.create_rectangle(
                legend_x, legend_y, legend_x + 15, legend_y + 15,
                fill=color, outline="black"
            )
            self.rack_canvas.create_text(
                legend_x + 20, legend_y + 7,
                text=item, font=("Arial", 8), anchor="w"
            )
            legend_x += 80
        
        # Instruções de uso para racks grandes
        if total_slots > 13:
            instructions_y = legend_y + 40
            instructions_x = max(300, total_width // 2)
            self.rack_canvas.create_text(
                instructions_x, instructions_y,
                text="💡 Dica: Use as setas do teclado ou arraste a barra de rolagem para navegar pelos slots",
                font=("Arial", 8), fill="blue", anchor="center"
            )
    
    def on_rack_slot_click(self, event):
        """Clique diretamente em um item de slot (robusto com scroll)."""
        try:
            # 'current' é o item sob o cursor já convertido pelo Tk
            current_items = self.rack_canvas.find_withtag("current")
            if not current_items:
                return
            tags = self.rack_canvas.gettags(current_items[0])
            slot_id = None
            for t in tags:
                if t.startswith("slot_"):
                    slot_id = t.replace("slot_", "")
                    break
            if not slot_id or slot_id not in self.rack_slots:
                return
            self.selected_slot = slot_id
            self.selected_slot_var.set(f"Slot {slot_id}")
            self.load_slot_properties()
            self.draw_rack_layout()
        except Exception as e:
            print(f"Erro na função on_rack_slot_click: {e}")

    def on_rack_canvas_click(self, event):
        """Chamado quando o canvas do rack é clicado"""
        # Converter coordenadas do evento para o espaço do canvas (considera scroll)
        cx = self.rack_canvas.canvasx(event.x)
        cy = self.rack_canvas.canvasy(event.y)

        self.rack_canvas.focus_set()

        # Preferir itens exatamente sob o ponto
        items = self.rack_canvas.find_overlapping(cx, cy, cx, cy)
        if not items:
            return
        
        # Priorizar itens com tag 'slot'
        slot_item = None
        for it in items:
            if "slot" in self.rack_canvas.gettags(it):
                slot_item = it
                break
        if slot_item is None:
            # Fallback: usar o mais próximo
            closest = self.rack_canvas.find_closest(cx, cy)
            if not closest:
                return
            slot_item = closest[0]

        tags = self.rack_canvas.gettags(slot_item)
        slot_id = None
        for tag in tags:
            if tag.startswith("slot_"):
                slot_id = tag.replace("slot_", "")
                break

        if slot_id and slot_id in self.rack_slots:
            self.selected_slot = slot_id
            self.selected_slot_var.set(f"Slot {slot_id}")
            self.load_slot_properties()
            self.draw_rack_layout()  # Redesenhar para mostrar seleção

    def load_slot_properties(self):
        """Carrega as propriedades do slot selecionado"""
        if not self.selected_slot or self.selected_slot not in self.rack_slots:
            return
        
        slot = self.rack_slots[self.selected_slot]
        
        # Carregar dados básicos
        self.slot_type_var.set(slot.get('type', 'EmptySlot'))
        self.slot_id_var.set(slot.get('id', ''))
        self.slot_name_var.set(slot.get('name', ''))
        self.slot_can_id_var.set(slot.get('canId', ''))
        self.slot_ref_id_var.set(slot.get('refId', ''))
        
        # Atualizar visibilidade dos campos
        self.update_slot_fields_visibility()
    
    def on_slot_id_change(self, event=None):
        """Chamado quando o ID do slot muda - preenche automaticamente os outros campos"""
        if not self.selected_slot or self.selected_slot not in self.rack_slots:
            return
        
        slot_id_text = self.slot_id_var.get().strip()
        slot_type = self.slot_type_var.get()
        
        if not slot_id_text or slot_type in ['EmptySlot', 'Psc']:
            return
        
        # Automatizar preenchimento baseado no tipo e ID
        if slot_type == 'Com':
            # COM: ID formato 01XXX
            # canId = últimos 4 dígitos
            # name = "COM" + canId
            # type = "COM_FSE" (fixo)
            # redundant = "NORMAL" (fixo)
            try:
                if len(slot_id_text) >= 4:
                    can_id = slot_id_text[1:]  # Retira o prefixo
                    while can_id[0] == '0':
                        can_id = can_id[1:]  # Retira zero à esquerda se houver

                    name = f"COM{can_id}"
                    
                    self.slot_can_id_var.set(can_id)
                    self.slot_name_var.set(name)
                    
                    # Atualizar dados no rack_slots
                    slot = self.rack_slots[self.selected_slot]
                    slot['canId'] = can_id
                    slot['name'] = name
                    slot['type_com'] = 'COM_FSE'
                    slot['redundant'] = 'NORMAL'
                    
            except ValueError:
                pass
                
        elif slot_type == 'Aeb':
            # AEB: ID formato 1XXXX
            # canId = últimos 4 dígitos
            # name = "AEB" + canId
            # refId = "2" + canId
            try:
                if len(slot_id_text) >= 4:
                    can_id = slot_id_text[1:]  # Remove o prefixo
                    ref_id = f"2{can_id}"
                    while can_id[0] == '0':
                        can_id = can_id[1:]  # Retira zero à esquerda se houver
                    name = f"AEB{can_id}"
                    
                    self.slot_can_id_var.set(can_id)
                    self.slot_name_var.set(name)
                    self.slot_ref_id_var.set(ref_id)
                    
                    # Atualizar dados no rack_slots
                    slot = self.rack_slots[self.selected_slot]
                    slot['canId'] = can_id
                    slot['name'] = name
                    slot['refId'] = ref_id
                    
            except ValueError:
                pass
                
        elif slot_type == 'IoExb':
            # IoExb: name sempre "IO-EXB", refId substitui primeiro dígito "5" por "2"
            try:
                name = "IO-EXB"  # Nome sempre fixo
                ref_id = ''
                
                # Calcular refId: substitui primeiro dígito "5" por "1"
                if slot_id_text.startswith('5') and len(slot_id_text) >= 2:
                    base_number = slot_id_text[1:]  # Remove o "5" inicial
                    ref_id = f'2{base_number}'  # Adiciona prefixo "2" (mesmo do sensor)
                else:
                    # Fallback: se não começa com 5, assumir que já é o número base
                    digits_only = ''.join(ch for ch in slot_id_text if ch.isdigit())
                    if digits_only:
                        ref_id = f'2{digits_only}'
                    else:
                        ref_id = slot_id_text  # Último fallback
                
                self.slot_name_var.set(name)
                self.slot_ref_id_var.set(ref_id)
                
                # Atualizar dados no rack_slots
                slot = self.rack_slots[self.selected_slot]
                slot['name'] = name
                slot['refId'] = ref_id
                    
            except ValueError:
                pass
        
        # Mostrar campos relevantes
        self.update_slot_fields_visibility()
        
        # Redesenhar o rack para mostrar as mudanças
        self.draw_rack_layout()

        # >>> sincronizar e atualizar lista
        self._sync_and_refresh_cubicles_list()
    
    def update_slot_fields_visibility(self):
        """Atualiza a visibilidade dos campos baseado no tipo do slot"""
        slot_type = self.slot_type_var.get()
        
        # Ocultar todos os campos primeiro
        self.name_label.grid_remove()
        self.name_entry.grid_remove()
        self.can_id_label.grid_remove()
        self.can_id_entry.grid_remove()
        self.ref_id_label.grid_remove()
        self.ref_id_entry.grid_remove()
        
        # Mostrar campos relevantes
        row = 3
        if slot_type in ['Com', 'Aeb', 'IoExb']:
            self.name_label.grid(row=row, column=0, sticky="w", pady=5)
            self.name_entry.grid(row=row, column=1, sticky="w", padx=5, pady=5)
            row += 1
        
        if slot_type in ['Com', 'Aeb']:
            self.can_id_label.grid(row=row, column=0, sticky="w", pady=5)
            self.can_id_entry.grid(row=row, column=1, sticky="w", padx=5, pady=5)
            row += 1
        
        if slot_type in ['Aeb', 'IoExb']:
            self.ref_id_label.grid(row=row, column=0, sticky="w", pady=5)
            self.ref_id_entry.grid(row=row, column=1, sticky="w", padx=5, pady=5)
    
    def on_slot_type_change(self, event=None):
        """Chamado quando o tipo do slot muda"""
        if not self.selected_slot:
            return
        
        slot_type = self.slot_type_var.get()
        
        # Não permitir PSC em slots diferentes do 1
        if slot_type == 'Psc' and self.selected_slot != '1':
            messagebox.showwarning("Aviso", "PSC só pode estar no Slot 1!")
            self.slot_type_var.set(self.rack_slots[self.selected_slot].get('type', 'EmptySlot'))
            return
        
        # Garantir que slot 1 sempre seja PSC
        if self.selected_slot == '1' and slot_type != 'Psc':
            messagebox.showwarning("Aviso", "Slot 1 deve sempre conter PSC!")
            self.slot_type_var.set('Psc')
            return
        
        # Limpar campos automáticos
        self.slot_name_var.set('')
        self.slot_can_id_var.set('')
        self.slot_ref_id_var.set('')
        
        # Atualizar visibilidade dos campos
        self.update_slot_fields_visibility()

        # Aplicar prefixo de ID conforme tipo
        self.enforce_slot_id_prefix()

        # Se há um ID e não é slot vazio/PSC, processar automaticamente
        if self.slot_id_var.get().strip() and slot_type not in ['EmptySlot', 'Psc']:
            self.on_slot_id_change()
    
    def apply_slot_changes(self):
        """Aplica as mudanças do slot selecionado"""
        if not self.selected_slot or self.selected_slot not in self.rack_slots:
            messagebox.showwarning("Aviso", "Nenhum slot selecionado.")
            return
        
        slot = self.rack_slots[self.selected_slot]
        
        # Atualizar dados básicos
        slot['type'] = self.slot_type_var.get()
        slot['id'] = self.slot_id_var.get()
        
        # Os demais campos são preenchidos automaticamente pelo on_slot_id_change
        # Apenas garantir que estão atualizados
        slot_type = slot['type']
        
        if slot_type == 'Com':
            # COM já tem type_com e redundant definidos automaticamente
            if 'type_com' not in slot:
                slot['type_com'] = 'COM_FSE'
            if 'redundant' not in slot:
                slot['redundant'] = 'NORMAL'
        elif slot_type == 'EmptySlot':
            # Remover campos não utilizados para slots vazios
            fields_to_remove = ['name', 'canId', 'refId', 'type_com', 'redundant']
            for field in fields_to_remove:
                slot.pop(field, None)
        elif slot_type == 'Psc':
            # PSC não precisa de campos extras
            fields_to_remove = ['name', 'canId', 'refId', 'type_com', 'redundant']
            for field in fields_to_remove:
                slot.pop(field, None)

        self.draw_rack_layout()

        # >>> sincronizar e atualizar lista
        self._sync_and_refresh_cubicles_list()
        self.rack_canvas.focus_set()
        self.refresh_cub_list()

        messagebox.showinfo("Sucesso", f"Slot {self.selected_slot} atualizado com dados automáticos!")
    
    def clear_selected_slot(self):
        """Limpa o slot selecionado"""
        if not self.selected_slot or self.selected_slot not in self.rack_slots:
            return
        
        if self.selected_slot == '1':
            messagebox.showwarning("Aviso", "Slot 1 deve sempre conter PSC!")
            return
        
        # Calcular base para IDs baseado no rack
        rack_id = self.rack_id_var.get()
        if rack_id.isdigit():
            base_id = int(rack_id)
        else:
            base_id = 8001
        
        # Limpar slot
        self.rack_slots[self.selected_slot] = {
            'id': f"{base_id + int(self.selected_slot) + 1:05d}",
            'type': 'EmptySlot',
            'slotId': self.selected_slot
        }
        
        self.load_slot_properties()
        self.draw_rack_layout()
        # >>> sincronizar e atualizar lista
        self._sync_and_refresh_cubicles_list()
        self.refresh_cub_list()
    
    def clear_rack(self):
        """Limpa todos os slots do rack (exceto PSC)"""
        if not self.rack_slots:
            return
        
        if messagebox.askyesno("Confirmar", "Limpar todos os slots (exceto PSC)?"):
            # Calcular base para IDs baseado no rack
            rack_id = self.rack_id_var.get()
            if rack_id.isdigit():
                base_id = int(rack_id)
            else:
                base_id = 8001
            
            for slot_id in self.rack_slots:
                if slot_id != '1':  # Manter PSC no slot 1
                    self.rack_slots[slot_id] = {
                        'id': f"{base_id + int(slot_id) + 1:05d}",
                        'type': 'EmptySlot',
                        'slotId': slot_id
                    }
            
            self.draw_rack_layout()
        # >>> sincronizar e atualizar lista
        self._sync_and_refresh_cubicles_list()
        self.refresh_cub_list()
    
    def validate_cubicle(self):
        """Valida o cubicle atual baseado nas configurações do FdsConfig"""
        if not getattr(self, 'current_cubicle', None):
            messagebox.showwarning("Aviso", "Nenhum cubículo selecionado.")
            return

        # Garantir que o modelo está sincronizado com a UI antes de validar
        self._sync_current_cubicle_from_editor()

        options = self._open_cubicle_validation_options_dialog()
        if not options:
            return

        report = self._run_cubicles_validation([self.current_cubicle], options)
        self._write_validation_output(report)

    def validate_all_cubicles(self):
        """Valida todos os cubículos carregados baseado nas configurações do FdsConfig"""
        if not getattr(self, 'cubicles_data', None) or len(self.cubicles_data) == 0:
            messagebox.showwarning("Aviso", "Nenhum cubículo carregado.")
            return

        # Se houver cubículo atual aberto no editor, sincronizar antes
        self._sync_current_cubicle_from_editor()

        options = self._open_cubicle_validation_options_dialog()
        if not options:
            return

        report = self._run_cubicles_validation(list(self.cubicles_data), options)
        self._write_validation_output(report)

    def _write_validation_output(self, text: str):
        try:
            if hasattr(self, 'validation_output_text') and self.validation_output_text:
                self.validation_output_text.delete(1.0, tk.END)
                self.validation_output_text.insert(tk.END, text)
                return
        except Exception:
            pass
        # Fallback
        messagebox.showinfo("Validação", text)

    def _open_cubicle_validation_options_dialog(self):
        """Abre uma janela simples para escolher quais comparações executar."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Comparações de Validação")
        dialog.geometry("520x340")
        dialog.transient(self.root)
        dialog.grab_set()

        # Estado (retorno)
        result = {'ok': False}

        # Fontes
        sources_frame = ttk.LabelFrame(dialog, text="Fontes", padding=10)
        sources_frame.pack(fill=tk.X, padx=10, pady=10)

        use_fdsconfig_var = tk.BooleanVar(value=True)
        use_cubicles_var = tk.BooleanVar(value=True)
        use_trackplan_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(sources_frame, text="FdsConfig", variable=use_fdsconfig_var).pack(anchor='w')
        ttk.Checkbutton(sources_frame, text="Cubículos", variable=use_cubicles_var).pack(anchor='w')

        # Trackplan ainda não implementado nesta validação (deixar visível para o fluxo futuro)
        cb_tp = ttk.Checkbutton(sources_frame, text="Trackplan (em desenvolvimento)", variable=use_trackplan_var)
        cb_tp.state(['disabled'])
        cb_tp.pack(anchor='w')

        # Regras
        rules_frame = ttk.LabelFrame(dialog, text="Regras", padding=10)
        rules_frame.pack(fill=tk.X, padx=10, pady=5)

        check_com_var = tk.BooleanVar(value=True)
        check_aeb_var = tk.BooleanVar(value=True)
        check_tracksection_var = tk.BooleanVar(value=True)

        ttk.Checkbutton(rules_frame, text="COMs (FdsConfig ↔ Cubículos)", variable=check_com_var).pack(anchor='w')
        ttk.Checkbutton(rules_frame, text="AEBs/CountingHead (FdsConfig ↔ Cubículos)", variable=check_aeb_var).pack(anchor='w')
        ttk.Checkbutton(
            rules_frame,
            text="TrackSection1/2 ⇒ Aeb + IoExb no mesmo cubículo",
            variable=check_tracksection_var
        ).pack(anchor='w')

        # Botões
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        def on_ok():
            result.update({
                'ok': True,
                'use_fdsconfig': bool(use_fdsconfig_var.get()),
                'use_cubicles': bool(use_cubicles_var.get()),
                'use_trackplan': bool(use_trackplan_var.get()),
                'check_com': bool(check_com_var.get()),
                'check_aeb': bool(check_aeb_var.get()),
                'check_tracksection': bool(check_tracksection_var.get()),
            })
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=on_cancel).pack(side=tk.RIGHT, padx=5)

        dialog.wait_window()
        if not result.get('ok'):
            return None
        return result

    def _run_cubicles_validation(self, cubicles, options):
        """Executa validações e retorna um relatório textual."""
        # Validar seleção de fontes
        if not options.get('use_fdsconfig', True) or not options.get('use_cubicles', True):
            return "Seleção inválida: para validar agora é necessário marcar FdsConfig e Cubículos."

        # Mapear elementos do FdsConfig
        fds_maps = self._index_fdsconfig_elements()
        if fds_maps is None:
            return "FdsConfig não carregado (ou sem gerador inicializado). Carregue um FdsConfig.xml primeiro."

        com_by_id = fds_maps['com_by_id']
        aeb_by_id = fds_maps['aeb_by_id']
        counting_by_id = fds_maps['counting_by_id']
        tracksection_ids = fds_maps['tracksection_ids']

        errors_total = 0
        warnings_total = 0
        lines = []

        def add_error(msg):
            nonlocal errors_total
            errors_total += 1
            lines.append(f"  - ❌ {msg}")

        def add_warn(msg):
            nonlocal warnings_total
            warnings_total += 1
            lines.append(f"  - ⚠️ {msg}")

        # Pré-computar presença por cubículo para a regra de TrackSection
        cubicle_presence = []  # list of (cubicle_label, aeb_set, ioexb_set, com_set)
        for cubicle in cubicles:
            label = self._format_cubicle_label(cubicle)
            aeb_set = set()
            ioexb_set = set()
            com_set = set()
            for _, slot in self._iter_cubicle_slots(cubicle):
                st = (slot.get('type') or '').strip()
                if st == 'Aeb':
                    bid = self._get_slot_base_id(slot, prefer='canId', prefixes=('1',))
                    if bid is not None:
                        aeb_set.add(bid)
                elif st == 'IoExb':
                    bid = self._get_slot_base_id(slot, prefer='id', prefixes=('5',), fallback_ref_prefixes=('2', '1'))
                    if bid is not None:
                        ioexb_set.add(bid)
                elif st == 'Com':
                    bid = self._get_slot_base_id(slot, prefer='canId', prefixes=('0',))
                    if bid is not None:
                        com_set.add(bid)
            cubicle_presence.append((label, aeb_set, ioexb_set, com_set))

        # Validação por cubículo
        for cubicle in cubicles:
            label = self._format_cubicle_label(cubicle)
            lines.append(f"{label}:")

            # Regras COM/AEB por slot
            for slot_id, slot in self._iter_cubicle_slots(cubicle):
                st = (slot.get('type') or '').strip()

                if st == 'Com' and options.get('check_com', True):
                    base_id = self._get_slot_base_id(slot, prefer='canId', prefixes=('0',))
                    if base_id is None:
                        add_error(f"Slot {slot_id}: COM sem base_id válido (canId/id).")
                        continue

                    fds_el = com_by_id.get(base_id)
                    if not fds_el:
                        add_error(f"Slot {slot_id}: COM base_id={base_id} não existe no FdsConfig (ComMaster).")
                        continue

                    expected_name = f"COM{base_id}"
                    slot_name = (slot.get('name') or '').strip()
                    if slot_name and slot_name != expected_name:
                        add_error(f"Slot {slot_id}: COM base_id={base_id} nome='{slot_name}' esperado='{expected_name}'.")
                    elif not slot_name:
                        add_warn(f"Slot {slot_id}: COM base_id={base_id} sem nome; esperado '{expected_name}'.")

                if st == 'Aeb' and options.get('check_aeb', True):
                    base_id = self._get_slot_base_id(slot, prefer='canId', prefixes=('1',))
                    if base_id is None:
                        add_error(f"Slot {slot_id}: AEB sem base_id válido (canId/id).")
                        continue

                    fds_aeb = aeb_by_id.get(base_id)
                    if not fds_aeb:
                        add_error(f"Slot {slot_id}: AEB base_id={base_id} não existe no FdsConfig (Aeb).")
                    fds_cnt = counting_by_id.get(base_id)
                    if not fds_cnt:
                        add_error(f"Slot {slot_id}: AEB base_id={base_id} sem CountingHead correspondente no FdsConfig.")

                    expected_name = f"AEB{base_id}"
                    slot_name = (slot.get('name') or '').strip()
                    if slot_name and slot_name != expected_name:
                        add_error(f"Slot {slot_id}: AEB base_id={base_id} nome='{slot_name}' esperado='{expected_name}'.")
                    elif not slot_name:
                        add_warn(f"Slot {slot_id}: AEB base_id={base_id} sem nome; esperado '{expected_name}'.")

                    # Validar refId: deve apontar para base_id (numérico), prefixo ideal '2'
                    ref_id_raw = (slot.get('refId') or '').strip()
                    if ref_id_raw:
                        ref_base = self._base_id_from_prefixed(ref_id_raw, prefixes=('2', '1'))
                        if ref_base is None:
                            add_error(f"Slot {slot_id}: AEB base_id={base_id} refId='{ref_id_raw}' inválido.")
                        elif ref_base != base_id:
                            add_error(f"Slot {slot_id}: AEB base_id={base_id} refId='{ref_id_raw}' (base {ref_base}) não confere.")
                        elif not ref_id_raw.startswith('2'):
                            add_warn(f"Slot {slot_id}: AEB base_id={base_id} refId='{ref_id_raw}' com prefixo inesperado (ideal '2').")
                    else:
                        add_warn(f"Slot {slot_id}: AEB base_id={base_id} sem refId; esperado '2...'.")

            # Regra TrackSection1/2 => Aeb + IoExb no mesmo cubículo
            if options.get('check_tracksection', True):
                # Construir sets do cubículo atual
                aeb_set = set()
                ioexb_set = set()
                for _, slot in self._iter_cubicle_slots(cubicle):
                    st = (slot.get('type') or '').strip()
                    if st == 'Aeb':
                        bid = self._get_slot_base_id(slot, prefer='canId', prefixes=('1',))
                        if bid is not None:
                            aeb_set.add(bid)
                    elif st == 'IoExb':
                        bid = self._get_slot_base_id(slot, prefer='id', prefixes=('5',), fallback_ref_prefixes=('2', '1'))
                        if bid is not None:
                            ioexb_set.add(bid)

                for ts_id in sorted(tracksection_ids):
                    if ts_id in aeb_set or ts_id in ioexb_set:
                        # Se apareceu algo deste base_id neste cubículo, ele precisa ter ambos
                        missing = []
                        if ts_id not in aeb_set:
                            missing.append('Aeb')
                        if ts_id not in ioexb_set:
                            missing.append('IoExb')
                        if missing:
                            add_error(
                                f"TrackSection base_id={ts_id}: neste cubículo faltando {', '.join(missing)} (devem estar juntos)."
                            )

        # Regra global de separação (TrackSection base_id com Aeb em um cubículo e IoExb em outro)
        if options.get('check_tracksection', True):
            lines.append("\nChecagem global TrackSection (separação entre cubículos):")
            for ts_id in sorted(tracksection_ids):
                cub_with_aeb = [label for (label, aebs, _, _) in cubicle_presence if ts_id in aebs]
                cub_with_io = [label for (label, _, ios, _) in cubicle_presence if ts_id in ios]
                cub_with_both = [label for (label, aebs, ios, _) in cubicle_presence if (ts_id in aebs and ts_id in ios)]

                if not cub_with_aeb and not cub_with_io:
                    # Se TrackSection existe no FdsConfig e não aparece em nenhum cubículo, é erro
                    errors_total += 1
                    lines.append(f"  - ❌ TrackSection base_id={ts_id}: não encontrado em nenhum cubículo (Aeb/IoExb ausentes).")
                    continue

                if cub_with_both:
                    # Mesmo que exista um cubículo com ambos, se houver outros com apenas um, é separação
                    others_aeb_only = [c for c in cub_with_aeb if c not in cub_with_both]
                    others_io_only = [c for c in cub_with_io if c not in cub_with_both]
                    if others_aeb_only or others_io_only:
                        errors_total += 1
                        lines.append(
                            f"  - ❌ TrackSection base_id={ts_id}: elementos separados entre cubículos. "
                            f"com ambos={cub_with_both} | só Aeb={others_aeb_only} | só IoExb={others_io_only}"
                        )
                else:
                    # Não há nenhum cubículo com ambos
                    errors_total += 1
                    lines.append(
                        f"  - ❌ TrackSection base_id={ts_id}: não existe cubículo com Aeb+IoExb juntos. "
                        f"Aeb em={cub_with_aeb} | IoExb em={cub_with_io}"
                    )

        header = [
            "=== Relatório de Validação ===",
            f"Cubículos verificados: {len(cubicles)}",
            f"Erros: {errors_total} | Avisos: {warnings_total}",
            "",
        ]
        return "\n".join(header + lines)

    def _index_fdsconfig_elements(self):
        """Indexa elementos do FdsConfig (via current_generator) por tipo e base_id."""
        gen = getattr(self, 'current_generator', None)
        if not gen:
            return None
        elements = getattr(gen, 'elements', None)
        if not elements:
            return None

        com_by_id = {}
        aeb_by_id = {}
        counting_by_id = {}
        tracksection_ids = set()

        for el in elements:
            element_type = (getattr(el, 'element_type', '') or '').strip()
            base_id = self._safe_int(getattr(el, 'element_id', None))
            if base_id is None:
                # fallback (caso venham strings)
                base_id = self._safe_int(str(getattr(el, 'element_id', '') or ''))

            if base_id is None or not element_type:
                continue

            if element_type == 'ComMaster':
                com_by_id[base_id] = el
            elif element_type == 'Aeb':
                aeb_by_id[base_id] = el
            elif element_type == 'CountingHead':
                counting_by_id[base_id] = el
            elif element_type in ('TrackSection1', 'TrackSection2'):
                tracksection_ids.add(base_id)

        return {
            'com_by_id': com_by_id,
            'aeb_by_id': aeb_by_id,
            'counting_by_id': counting_by_id,
            'tracksection_ids': tracksection_ids,
        }

    def _format_cubicle_label(self, cubicle: dict) -> str:
        cid = (cubicle or {}).get('id', '')
        name = (cubicle or {}).get('name', '')
        if cid and name:
            return f"[Cubículo id={cid} name={name}]"
        if cid:
            return f"[Cubículo id={cid}]"
        if name:
            return f"[Cubículo name={name}]"
        return "[Cubículo sem id/nome]"

    def _iter_cubicle_slots(self, cubicle: dict):
        rack = (cubicle or {}).get('rack', {}) or {}
        bp = (rack.get('bp', {}) or {})
        slots = (bp.get('slots', {}) or {})
        # slots é dict slotId->slot_data
        for slot_id in sorted(slots.keys(), key=lambda x: int(str(x)) if str(x).isdigit() else str(x)):
            yield slot_id, slots[slot_id]

    def _safe_int(self, value):
        if value is None:
            return None
        if isinstance(value, int):
            return value
        s = str(value).strip()
        if not s:
            return None
        digits = ''.join(ch for ch in s if ch.isdigit())
        if not digits:
            return None
        try:
            return int(digits)
        except Exception:
            return None

    def _base_id_from_prefixed(self, value: str, prefixes=('0', '1', '2', '3', '4', '5')):
        """Extrai base_id numérico de strings como '1001', '20001', etc. Remove prefixo se presente."""
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        # Remove prefixo 0/1/2/3/4/5 quando aplicável
        if s[0] in prefixes and len(s) > 1:
            s = s[1:]
        # Remover zeros à esquerda
        s = s.lstrip('0') or '0'
        try:
            return int(s)
        except Exception:
            return None

    def _get_slot_base_id(self, slot: dict, prefer='canId', prefixes=('0', '1', '2', '3', '4', '5'), fallback_ref_prefixes=('2', '1')):
        """Obtém base_id do slot com heurísticas estáveis para Com/Aeb/IoExb."""
        if not slot:
            return None

        # Preferência principal
        if prefer == 'canId':
            can_id = self._safe_int(slot.get('canId'))
            if can_id is not None:
                return can_id
            
        if prefer == 'id':
            sid = slot.get('id')
            if sid:
                bid = self._base_id_from_prefixed(str(sid), prefixes=prefixes)
                if bid is not None:
                    return bid

        # Fallbacks: tentar canId, id, refId
        can_id = self._safe_int(slot.get('canId'))
        if can_id is not None:
            return can_id

        sid = slot.get('id')
        if sid:
            bid = self._base_id_from_prefixed(str(sid), prefixes=prefixes)
            if bid is not None:
                return bid

        ref_id = slot.get('refId')
        if ref_id:
            bid = self._base_id_from_prefixed(str(ref_id), prefixes=fallback_ref_prefixes)
            if bid is not None:
                return bid

        return None

    # === EXPORTAÇÃO DO FDSCONFIG → CRIAÇÃO DE CUBÍCULOS/SLOTS (SEPARAÇÃO MANUAL) ===

    def _base4(self, n: int) -> str:
        return f"{int(n):04d}"

    def _can_id_str(self, base_id: int) -> str:
        """CAN ID no padrão usado na UI (sem zeros à esquerda)."""
        try:
            return str(int(self._base4(base_id)))
        except Exception:
            return str(base_id)

    def _slot_payload_for(self, slot_kind: str, base_id: int) -> dict:
        """Cria payload de slot para tipos Com/Aeb/IoExb baseado no base_id do FdsConfig."""
        b4 = self._base4(base_id)
        can_id = self._can_id_str(base_id)

        if slot_kind == 'Com':
            return {
                'type': 'Com',
                'id': f"0{b4}",
                'name': f"COM{can_id}",
                'canId': can_id,
                'type_com': 'COM_FSE',
                'redundant': 'NORMAL',
            }

        if slot_kind == 'Aeb':
            return {
                'type': 'Aeb',
                'id': f"1{b4}",
                'name': f"AEB{can_id}",
                'canId': can_id,
                # refId (CountingHead) segue o padrão do editor: 2 + base4
                'refId': f"2{b4}",
            }

        if slot_kind == 'IoExb':
            return {
                'type': 'IoExb',
                'id': f"5{b4}",
                'name': 'IO-EXB',
                # refId do IoExb no editor atual é 1 + base4
                'refId': f"2{b4}",
            }

        return {'type': 'EmptySlot'}

    def _make_cubicle_template(self, idx: int, name: str, height: str, bp_size: int):
        """Cria estrutura base de cubículo (com PSC no slot 1)."""
        new_id = str(9000 + (idx + 1))

        next_rack_base = (8000 + 100 * idx + (72000 if idx > 9 else 0)) + 1
        rack_id = str(next_rack_base)
        bp_id = str(next_rack_base + 1)

        cubicle = {
            'id': new_id,
            'name': name,
            'height': str(height or '1'),
            'rack': {
                'id': rack_id,
                'bp': {
                    'id': bp_id,
                    'size': str(bp_size),
                    'startSlot': '1',
                    'slots': {},
                }
            }
        }

        # Inicializar slots vazios
        for i in range(1, bp_size + 1):
            cubicle['rack']['bp']['slots'][str(i)] = {
                'id': f"{next_rack_base + i + 1:05d}",
                'type': 'EmptySlot',
                'slotId': str(i)
            }

        # PSC no slot 1
        cubicle['rack']['bp']['slots']['1'] = {
            'id': str(next_rack_base + 2),
            'type': 'Psc',
            'slotId': '1'
        }

        return cubicle

    def _create_cubicle_from_assignment(self, idx: int, meta: dict, assigned_items: list):
        """Cria cubículo a partir de itens escolhidos pelo usuário (ordem do usuário = ordem dos slots)."""
        name = (meta.get('name') or f"CUBICLE-{idx + 1}").strip()
        height = str(meta.get('height') or '1').strip()

        # Itens que ocupam posição de slot (permite "gaps" com EmptySlot)
        slot_positions = [it for it in assigned_items if it.get('kind') in ('Com', 'Aeb', 'IoExb', 'EmptySlot')]
        required_size = max(1, 1 + len(slot_positions))

        bp_size = self._safe_int(meta.get('bp_size')) or required_size
        if bp_size < required_size:
            bp_size = required_size

        cub = self._make_cubicle_template(idx=idx, name=name, height=height, bp_size=bp_size)

        write_slot = 2
        for it in assigned_items:
            kind = it.get('kind')
            if kind == 'TrackSection':
                continue
            if kind == 'EmptySlot':
                write_slot += 1
                continue
            if kind in ('Com', 'Aeb', 'IoExb'):
                payload = self._slot_payload_for(kind, it['base_id'])
                payload['slotId'] = str(write_slot)
                cub['rack']['bp']['slots'][str(write_slot)] = payload
                write_slot += 1

        return cub

    def _validate_export_plan(self, planned_cubicles: list, tracksection_ids: set, com_ids: set, aeb_ids: set):
        """Valida se todos os itens do FdsConfig foram alocados e se TrackSection tem Aeb+IoExb no mesmo cubículo."""
        # Mapear presença por base_id
        com_assigned = set()
        aeb_assigned = set()
        ts_seen = set()
        ts_ok = set()  # base_id com Aeb+IoExb juntos no mesmo cubículo

        for item in planned_cubicles:
            assigned = item.get('assigned', []) or []
            aeb_set = set(it['base_id'] for it in assigned if it.get('kind') == 'Aeb')
            io_set = set(it['base_id'] for it in assigned if it.get('kind') == 'IoExb')
            com_set = set(it['base_id'] for it in assigned if it.get('kind') == 'Com')
            # TrackSection pode não aparecer explicitamente na UI; inferir por Aeb/IoExb dentro dos IDs de TS
            ts_set = (aeb_set | io_set) & set(tracksection_ids)

            com_assigned |= com_set
            aeb_assigned |= aeb_set
            ts_seen |= ts_set

            for bid in ts_set:
                if bid in aeb_set and bid in io_set:
                    ts_ok.add(bid)

        missing_com = sorted(com_ids - com_assigned)
        missing_aeb = sorted(aeb_ids - aeb_assigned)
        missing_ts = sorted(tracksection_ids - ts_seen)
        broken_ts = sorted(tracksection_ids - ts_ok)

        problems = []
        if missing_com:
            problems.append(f"COMs não alocados: {missing_com}")
        if missing_aeb:
            problems.append(f"AEBs não alocados: {missing_aeb}")
        if missing_ts:
            problems.append(f"TrackSection1/2 não alocados: {missing_ts}")
        if broken_ts:
            problems.append(f"TrackSection sem Aeb+IoExb juntos no mesmo cubículo: {broken_ts}")

        if problems:
            return False, "\n".join(problems)
        return True, ""

    def open_fdsconfig_export_wizard(self):
        """Wizard: usuário separa elementos do FdsConfig por cubículo; o sistema cria cubículos e slots."""
        fds_maps = self._index_fdsconfig_elements()
        if fds_maps is None:
            messagebox.showwarning("Aviso", "FdsConfig não carregado. Carregue um FdsConfig.xml primeiro.")
            return

        com_ids = set(fds_maps['com_by_id'].keys())
        aeb_ids = set(fds_maps['aeb_by_id'].keys())
        tracksection_ids = set(fds_maps['tracksection_ids'])

        # Filtrar itens já usados nos cubículos atuais (para não reaparecerem depois)
        used_com_ids = set()
        used_aeb_ids = set()
        used_tracksection_ids = set()
        try:
            for cub in (self.cubicles_data or []):
                for _, slot in self._iter_cubicle_slots(cub):
                    if not slot:
                        continue
                    stype = slot.get('type')
                    if stype == 'Com':
                        bid = self._get_slot_base_id(slot, prefer='canId', prefixes=('0',), fallback_ref_prefixes=('0',))
                        if bid is not None:
                            used_com_ids.add(bid)
                    elif stype == 'Aeb':
                        bid = self._get_slot_base_id(slot, prefer='canId', prefixes=('1',), fallback_ref_prefixes=('2', '1'))
                        if bid is not None:
                            used_aeb_ids.add(bid)
                            used_tracksection_ids.add(bid)
                    elif stype == 'IoExb':
                        bid = self._get_slot_base_id(slot, prefer='id', prefixes=('5',), fallback_ref_prefixes=('2', '1'))
                        if bid is not None:
                            used_tracksection_ids.add(bid)
        except Exception:
            # Se algo der errado na leitura dos cubículos atuais, não bloqueia o wizard
            used_com_ids = set()
            used_aeb_ids = set()
            used_tracksection_ids = set()

        available = []
        for base_id in sorted(com_ids):
            if base_id in used_com_ids:
                continue
            available.append({'kind': 'Com', 'base_id': base_id, 'label': f"COM {self._base4(base_id)} (ComMaster)"})
        for base_id in sorted(aeb_ids):
            if base_id in used_aeb_ids:
                continue
            available.append({'kind': 'Aeb', 'base_id': base_id, 'label': f"AEB {self._base4(base_id)} (Aeb)"})
        for base_id in sorted(tracksection_ids):
            if base_id in used_tracksection_ids:
                continue
            available.append({'kind': 'TrackSection', 'base_id': base_id, 'label': f"TS {self._base4(base_id)} (TrackSection1/2)"})

        if not available:
            messagebox.showinfo("Exportar do FdsConfig", "Nenhum elemento ComMaster/Aeb/TrackSection1/2 encontrado no FdsConfig.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Exportar do FdsConfig → Criar cubículos")
        dialog.geometry("980x620")
        dialog.transient(self.root)
        dialog.grab_set()

        planned_cubicles = []  # lista de {'meta':..., 'assigned':...}
        assigned = []  # itens do cubículo atual

        top = ttk.Frame(dialog, padding=10)
        top.pack(fill=tk.X)

        replace_existing_var = tk.BooleanVar(value=False)
        auto_complete_ts_var = tk.BooleanVar(value=True)
        partial_import_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Substituir cubículos existentes", variable=replace_existing_var).pack(side=tk.LEFT, padx=(0, 20))
        ttk.Checkbutton(top, text="Auto-completar TrackSection (Aeb + IoExb no mesmo cubículo)", variable=auto_complete_ts_var).pack(side=tk.LEFT)
        ttk.Checkbutton(top, text="Importação parcial (não exigir alocar tudo)", variable=partial_import_var).pack(side=tk.LEFT, padx=(20, 0))

        meta_frame = ttk.LabelFrame(dialog, text="Dados do cubículo atual", padding=10)
        meta_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        name_var = tk.StringVar(value="")
        height_var = tk.StringVar(value="1")
        bp_size_var = tk.StringVar(value="13")

        ttk.Label(meta_frame, text="Nome:").grid(row=0, column=0, sticky="w")
        ttk.Entry(meta_frame, textvariable=name_var, width=35).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(meta_frame, text="Altura:").grid(row=0, column=2, sticky="w", padx=(20, 0))
        ttk.Entry(meta_frame, textvariable=height_var, width=8).grid(row=0, column=3, sticky="w", padx=8)
        ttk.Label(meta_frame, text="Tamanho BP (slots):").grid(row=0, column=4, sticky="w", padx=(20, 0))
        ttk.Entry(meta_frame, textvariable=bp_size_var, width=8).grid(row=0, column=5, sticky="w", padx=8)
        meta_frame.grid_columnconfigure(6, weight=1)

        mid = ttk.Frame(dialog, padding=10)
        mid.pack(fill=tk.BOTH, expand=True)

        left = ttk.LabelFrame(mid, text="Elementos disponíveis (FdsConfig)", padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        center = ttk.Frame(mid)
        center.pack(side=tk.LEFT, fill=tk.Y, padx=10)
        right = ttk.LabelFrame(mid, text="Elementos no cubículo atual (ordem = slots)", padding=10)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        avail_list = tk.Listbox(left, height=18, selectmode=tk.EXTENDED)
        avail_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        avail_scroll = ttk.Scrollbar(left, orient="vertical", command=avail_list.yview)
        avail_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        avail_list.configure(yscrollcommand=avail_scroll.set)

        assigned_list = tk.Listbox(right, height=18, selectmode=tk.EXTENDED)
        assigned_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        assigned_scroll = ttk.Scrollbar(right, orient="vertical", command=assigned_list.yview)
        assigned_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        assigned_list.configure(yscrollcommand=assigned_scroll.set)

        def refresh_lists():
            avail_list.delete(0, tk.END)
            for it in available:
                avail_list.insert(tk.END, it['label'])
            assigned_list.delete(0, tk.END)
            for it in assigned:
                assigned_list.insert(tk.END, it['label'])

        def remove_available_aeb(base_id: int):
            for i, it in enumerate(list(available)):
                if it.get('kind') == 'Aeb' and it.get('base_id') == base_id:
                    return available.pop(i)
            return None

        def remove_available_ts(base_id: int):
            for i, it in enumerate(list(available)):
                if it.get('kind') == 'TrackSection' and it.get('base_id') == base_id:
                    return available.pop(i)
            return None

        def add_back_available(item: dict):
            if not item:
                return
            available.append(item)
            available.sort(key=lambda x: (x.get('kind', ''), x.get('base_id', 0)))

        def ensure_assigned(kind: str, base_id: int, label: str):
            for it in assigned:
                if it.get('kind') == kind and it.get('base_id') == base_id:
                    return
            assigned.append({'kind': kind, 'base_id': base_id, 'label': label})

        def on_add_empty_slot():
            assigned.append({'kind': 'EmptySlot', 'base_id': -1, 'label': "[GAP] EmptySlot"})
            refresh_lists()

        def on_add():
            sel = list(avail_list.curselection())
            if not sel:
                return

            # Processar em ordem decrescente para pop() não bagunçar índices
            for idx0 in sel:
                if idx0 < 0 or idx0 >= len(available):
                    continue
                it = available.pop(idx0)
                kind = it.get('kind')
                bid = it.get('base_id')

                # TrackSection: NÃO entra na lista do cubículo. Ao selecionar TS, adiciona apenas IoExb (e Aeb opcional).
                if kind == 'TrackSection':
                    # Sempre adiciona IoExb para esse base_id
                    ensure_assigned('IoExb', bid, f"[TS] IO-EXB {self._base4(bid)} (IoExb)")
                    if bool(auto_complete_ts_var.get()):
                        removed_aeb = remove_available_aeb(bid)
                        if removed_aeb:
                            ensure_assigned('Aeb', bid, f"[TS] AEB {self._base4(bid)} (Aeb)")
                        else:
                            ensure_assigned('Aeb', bid, f"[TS] AEB {self._base4(bid)} (Aeb)")
                    continue

                assigned.append(it)

            refresh_lists()

        def on_remove():
            sel = list(assigned_list.curselection())
            if not sel:
                return

            removed_items = []
            for idx0 in sorted((int(i) for i in sel), reverse=True):
                if idx0 < 0 or idx0 >= len(assigned):
                    continue
                removed_items.append(assigned.pop(idx0))

            # devolver ao disponível itens que existiam no FdsConfig (Com/Aeb/TrackSection). IoExb não existe como item avulso.
            for it in removed_items:
                if not it:
                    continue
                label = str(it.get('label', ''))
                kind = it.get('kind')
                bid = it.get('base_id')

                if kind == 'EmptySlot':
                    continue

                # Se era IO-EXB vindo de TS, devolve TrackSection para o disponível
                if kind == 'IoExb' and label.startswith('[TS]') and bid is not None and bid != -1:
                    add_back_available({'kind': 'TrackSection', 'base_id': bid, 'label': f"TS {self._base4(bid)} (TrackSection1/2)"})
                    continue

                # Devolver Com/Aeb normalmente
                if kind in ('Com', 'Aeb') and bid is not None and bid != -1:
                    add_back_available({'kind': kind, 'base_id': bid, 'label': it.get('label', '')})

            refresh_lists()

        def on_up():
            sel = assigned_list.curselection()
            if not sel:
                return
            i = int(sel[0])
            if i <= 0:
                return
            assigned[i - 1], assigned[i] = assigned[i], assigned[i - 1]
            refresh_lists()
            assigned_list.selection_set(i - 1)

        def on_down():
            sel = assigned_list.curselection()
            if not sel:
                return
            i = int(sel[0])
            if i >= len(assigned) - 1:
                return
            assigned[i + 1], assigned[i] = assigned[i], assigned[i + 1]
            refresh_lists()
            assigned_list.selection_set(i + 1)

        # Drag-and-drop simples para reordenar itens no cubículo atual
        drag_state = {'active': False, 'start_index': None}

        def _assigned_index_at_event(event):
            try:
                return int(assigned_list.nearest(event.y))
            except Exception:
                return None

        def on_drag_start(event):
            idx = _assigned_index_at_event(event)
            if idx is None or idx < 0 or idx >= len(assigned):
                drag_state['active'] = False
                drag_state['start_index'] = None
                return
            drag_state['active'] = True
            drag_state['start_index'] = idx

        def on_drag_motion(event):
            if not drag_state.get('active'):
                return
            src = drag_state.get('start_index')
            dst = _assigned_index_at_event(event)
            if src is None or dst is None:
                return
            if dst < 0 or dst >= len(assigned) or src < 0 or src >= len(assigned):
                return
            if dst == src:
                return
            item = assigned.pop(src)
            assigned.insert(dst, item)
            drag_state['start_index'] = dst
            refresh_lists()
            assigned_list.selection_clear(0, tk.END)
            assigned_list.selection_set(dst)

        def on_drag_end(event):
            drag_state['active'] = False
            drag_state['start_index'] = None

        assigned_list.bind('<ButtonPress-1>', on_drag_start)
        assigned_list.bind('<B1-Motion>', on_drag_motion)
        assigned_list.bind('<ButtonRelease-1>', on_drag_end)

        ttk.Button(center, text="Adicionar →", command=on_add).pack(fill=tk.X, pady=(0, 8))
        ttk.Button(center, text="← Remover", command=on_remove).pack(fill=tk.X, pady=(0, 20))
        ttk.Button(center, text="Inserir vazio", command=on_add_empty_slot).pack(fill=tk.X, pady=(0, 20))
        ttk.Button(center, text="↑ Subir", command=on_up).pack(fill=tk.X, pady=(0, 8))
        ttk.Button(center, text="↓ Descer", command=on_down).pack(fill=tk.X)

        bottom = ttk.Frame(dialog, padding=10)
        bottom.pack(fill=tk.X)

        planned_var = tk.StringVar(value="Cubículos na fila: 0")
        ttk.Label(bottom, textvariable=planned_var).pack(side=tk.LEFT)

        def update_planned_label():
            planned_var.set(f"Cubículos na fila: {len(planned_cubicles)}")

        def add_current_cubicle_to_queue():
            slot_items = [it for it in assigned if it.get('kind') in ('Com', 'Aeb', 'IoExb')]
            if not slot_items:
                messagebox.showwarning("Aviso", "Adicione pelo menos um COM/AEB/IoExb ao cubículo atual.")
                return

            planned_cubicles.append({
                'meta': {
                    'name': name_var.get(),
                    'height': height_var.get(),
                    'bp_size': bp_size_var.get(),
                },
                'assigned': copy.deepcopy(assigned),
            })

            # Reset para próximo cubículo
            name_var.set("")
            height_var.set("1")
            bp_size_var.set("13")
            assigned.clear()
            update_planned_label()
            refresh_lists()

        def finalize_and_apply():
            # Oferecer adicionar o cubículo atual se ainda há itens
            if assigned:
                if messagebox.askyesno("Concluir", "Você ainda tem elementos no cubículo atual. Deseja adicioná-lo à fila antes de concluir?"):
                    add_current_cubicle_to_queue()

            if not planned_cubicles:
                messagebox.showwarning("Aviso", "Nenhum cubículo na fila para criar.")
                return

            # Validação do plano:
            # - Em importação parcial: não exige alocar todos os itens; apenas bloqueia duplicatas e garante regra de TrackSection
            # - Em importação completa: mantém regra anterior (alocar tudo)
            if bool(partial_import_var.get()):
                # Duplicatas (mesmo tipo + base_id) dentro do plano
                seen = set()
                dups = []
                for ci, item in enumerate(planned_cubicles):
                    for it in (item.get('assigned', []) or []):
                        kind = it.get('kind')
                        if kind not in ('Com', 'Aeb', 'TrackSection', 'IoExb'):
                            continue
                        bid = it.get('base_id')
                        if bid is None or bid == -1:
                            continue
                        key = (kind, bid)
                        if key in seen:
                            dups.append(f"{kind} {self._base4(bid)}")
                        seen.add(key)

                if dups:
                    messagebox.showerror("Plano inválido", "Itens duplicados no plano (mesmo tipo/base_id):\n\n" + "\n".join(sorted(set(dups))))
                    return

                # Regra TrackSection1/2: se um base_id de TrackSection aparece (via TrackSection/Aeb/IoExb), deve ter Aeb+IoExb no mesmo cubículo
                aeb_owner = {}
                io_owner = {}
                broken = []
                for ci, item in enumerate(planned_cubicles):
                    a = item.get('assigned', []) or []
                    aeb_set = set(it['base_id'] for it in a if it.get('kind') == 'Aeb')
                    io_set = set(it['base_id'] for it in a if it.get('kind') == 'IoExb')
                    relevant = (aeb_set | io_set) & set(tracksection_ids)
                    for bid in relevant:
                        if bid not in aeb_set or bid not in io_set:
                            broken.append(f"TS {self._base4(bid)}: falta Aeb ou IoExb no mesmo cubículo")
                        if bid in aeb_set:
                            aeb_owner.setdefault(bid, ci)
                        if bid in io_set:
                            io_owner.setdefault(bid, ci)

                # separação entre cubículos (Aeb num, IoExb noutro) também é erro
                for bid in set(aeb_owner.keys()) | set(io_owner.keys()):
                    if bid in aeb_owner and bid in io_owner and aeb_owner[bid] != io_owner[bid]:
                        broken.append(f"TS {self._base4(bid)}: Aeb e IoExb estão em cubículos diferentes")

                if broken:
                    messagebox.showerror("Plano inválido", "Regra de TrackSection1/2 violada:\n\n" + "\n".join(sorted(set(broken))))
                    return
            else:
                ok, msg = self._validate_export_plan(planned_cubicles, tracksection_ids, com_ids, aeb_ids)
                if not ok:
                    messagebox.showerror("Plano inválido", f"O plano de exportação está incompleto/ inválido:\n\n{msg}")
                    return

            if bool(replace_existing_var.get()):
                self.cubicles_data.clear()

            start_idx = len(self.cubicles_data)
            for i, item in enumerate(planned_cubicles):
                cub = self._create_cubicle_from_assignment(
                    idx=start_idx + i,
                    meta=item['meta'],
                    assigned_items=item['assigned']
                )
                self.cubicles_data.append(cub)

            try:
                self.renumber_cubicles_by_position()
            except Exception:
                pass
            try:
                self.renumber_psc_and_empty()
            except Exception:
                pass

            self.update_cubicles_list()
            dialog.destroy()
            messagebox.showinfo("Exportar do FdsConfig", f"Cubículos criados: {len(planned_cubicles)}\nTotal atual: {len(self.cubicles_data)}")

        ttk.Button(bottom, text="Adicionar cubículo à fila", command=add_current_cubicle_to_queue).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom, text="Concluir", command=finalize_and_apply).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        update_planned_label()
        refresh_lists()
        dialog.wait_window()

    def apply_fdsconfig_to_cubicles(self):
        """Exportar do FdsConfig: cria cubículos e slots conforme separação feita pelo usuário."""
        return self.open_fdsconfig_export_wizard()

    def normalize_fdsconfig_to_cubicles(self):
        """Normaliza dados dos slots existentes (nome/canId/refId) usando o FdsConfig.

        Mantida para uso futuro; não é a ação do botão "Exportar do FdsConfig".
        """
        fds_maps = self._index_fdsconfig_elements()
        if fds_maps is None:
            messagebox.showwarning("Aviso", "FdsConfig não carregado. Carregue um FdsConfig.xml primeiro.")
            return

        com_by_id = fds_maps['com_by_id']
        aeb_by_id = fds_maps['aeb_by_id']

        def base4(n: int) -> str:
            return f"{int(n):04d}"

        def set_if_diff(d: dict, k: str, v) -> int:
            if d.get(k) != v:
                d[k] = v
                return 1
            return 0

        changed = 0
        for cubicle in self.cubicles_data:
            for _, slot in self._iter_cubicle_slots(cubicle):
                if not slot or slot.get('type') in ('EmptySlot', 'Psc', None, ''):
                    continue
                stype = slot.get('type')

                if stype == 'Com':
                    bid = self._get_slot_base_id(slot, prefer='canId', prefixes=('0',), fallback_ref_prefixes=('0',))
                    if bid is None or bid not in com_by_id:
                        continue
                    b4 = base4(bid)
                    changed += set_if_diff(slot, 'id', f"0{b4}")
                    changed += set_if_diff(slot, 'name', f"COM{self._can_id_str(bid)}")
                    changed += set_if_diff(slot, 'canId', self._can_id_str(bid))
                    changed += set_if_diff(slot, 'type_com', 'COM_FSE')
                    changed += set_if_diff(slot, 'redundant', 'NORMAL')

                elif stype == 'Aeb':
                    bid = self._get_slot_base_id(slot, prefer='canId', prefixes=('1',), fallback_ref_prefixes=('2', '1'))
                    if bid is None or bid not in aeb_by_id:
                        continue
                    b4 = base4(bid)
                    changed += set_if_diff(slot, 'id', f"1{b4}")
                    changed += set_if_diff(slot, 'name', f"AEB{self._can_id_str(bid)}")
                    changed += set_if_diff(slot, 'canId', self._can_id_str(bid))
                    changed += set_if_diff(slot, 'refId', f"2{b4}")

                elif stype == 'IoExb':
                    bid = self._get_slot_base_id(slot, prefer='id', prefixes=('5',), fallback_ref_prefixes=('2', '1'))
                    if bid is None:
                        continue
                    b4 = base4(bid)
                    changed += set_if_diff(slot, 'id', f"5{b4}")
                    changed += set_if_diff(slot, 'name', "IO-EXB")
                    changed += set_if_diff(slot, 'refId', f"2{b4}")

        if changed:
            self.update_cubicles_list()
            messagebox.showinfo("Normalização", f"Slots normalizados: {changed}")
        else:
            messagebox.showinfo("Normalização", "Nenhuma alteração necessária.")

    def generate_cubicle_xml(self, fds_model="FDS101"):
        """Gera o XML do cubicle atual"""
        if not self.current_cubicle:
            self.xml_preview_text.delete(1.0, tk.END)
            self.xml_preview_text.insert(tk.END, "Nenhum cubicle selecionado.")
            return
        
        try:
            # Garantir que o modelo está sincronizado com a UI
            self._sync_current_cubicle_from_editor()

            xml_lines = []
            cubicle = self.current_cubicle
            
            # Abrir Cubicle

            xml_lines.append('<Cubicles>')

            xml_lines.append(f'\t<Cubicle height="{cubicle.get("height", "1")}" id="{cubicle.get("id", "")}" name="{cubicle.get("name", "")}">')
            
            rack = cubicle.get('rack', {})
            xml_lines.append(f'\t\t<Rack id="{rack.get("id", "")}">')
            
            bp = rack.get('bp', {})
            xml_lines.append(f'\t\t\t<Bp id="{bp.get("id", "")}" size="{bp.get("size", "13")}" startSlot="{bp.get("startSlot", "1")}">')
            
            # Ordenar slots por número
            slots = bp.get('slots', {})
            sorted_slots = sorted(slots.items(), key=lambda x: int(x[0]))
            
            for slot_id, slot in sorted_slots:
                slot_type = slot.get('type', 'EmptySlot')
                slot_xml_id = slot.get('id', '')
                
                if slot_type == 'Psc':
                    xml_lines.append(f'\t\t\t\t<Psc id="{slot_xml_id}" slotId="{slot_id}" />')
                
                elif slot_type == 'Com':
                    attributes = [
                        f'id="{slot_xml_id}"',
                        f'canId="{slot.get("canId", "")}"',
                        f'type="COM_FSE"',
                        f'redundant="NORMAL"',
                        f'name="{slot.get("name", "")}"',
                        f'slotId="{slot_id}"'
                    ]
                    xml_lines.append(f'\t\t\t\t<Com {" ".join(attributes)}>')
                    xml_lines.append('\t\t\t\t</Com>')
                
                elif slot_type == 'Aeb':
                    attributes = [
                        f'id="{slot_xml_id}"',
                        f'name="{slot.get("name", "")}"',
                        f'canId="{slot.get("canId", "")}"',
                        f'refId="{slot.get("refId", "")}"',
                        f'slotId="{slot_id}"'
                    ]
                    xml_lines.append(f'\t\t\t\t<Aeb {" ".join(attributes)} />')
                
                elif slot_type == 'IoExb':
                    attributes = [
                        f'id="{slot_xml_id}"',
                        f'name="IO-EXB"',
                        f'refId="{slot.get("refId", "")}"',
                        f'slotId="{slot_id}"',
                    ]
                    if self.fds_model == "FDS102":
                        xml_lines.append(f'\t\t\t\t<IoExb {" ".join(attributes)}>')
                        fma0 = f'3{slot_xml_id[1:]}'
                        fma1 = f'4{slot_xml_id[1:]}'
                        xml_lines.append(f'\t\t\t\t\t<TrackSectionExtern>')
                        xml_lines.append(f'\t\t\t\t\t\t<FmaExtern refId={fma0}/>')
                        xml_lines.append(f'\t\t\t\t\t\t<FmaExtern refId={fma1}/>')
                        xml_lines.append(f'\t\t\t\t\t</TrackSectionExtern>')
                        xml_lines.append(f'\t\t\t\t</IoExb>')
                    else:
                        xml_lines.append(f'\t\t\t\t<IoExb {" ".join(attributes)} />')

                elif slot_type == 'EmptySlot':
                    xml_lines.append(f'\t\t\t\t<EmptySlot id="{slot_xml_id}" slotId="{slot_id}" />')
            
            xml_lines.append('\t\t\t</Bp>')
            xml_lines.append('\t\t</Rack>')
            xml_lines.append('\t</Cubicle>')
            xml_lines.append('</Cubicles>')
            
            xml_content = '\n'.join(xml_lines)
            
            self.xml_preview_text.delete(1.0, tk.END)
            self.xml_preview_text.insert(tk.END, xml_content)
            
        except Exception as e:
            self.xml_preview_text.delete(1.0, tk.END)
            self.xml_preview_text.insert(tk.END, f"Erro ao gerar XML: {str(e)}")

    def generate_all_cubicles_xml(self):
        """Gera o XML completo de todos os cubicles"""
        if not self.cubicles_data:
            self.xml_preview_text.delete(1.0, tk.END)
            self.xml_preview_text.insert(tk.END, "Nenhum cubicle disponível para gerar XML.")
            return
        
        try:
            # IDs garantidos por posição
            self.renumber_cubicles_by_position()

            xml_lines = []
            xml_lines.append('\t<Cubicles>')
            
            for cubicle in self.cubicles_data:
                xml_lines.append(f'\t\t<Cubicle height="{cubicle.get("height", "1")}" id="{cubicle.get("id", "")}" name="{cubicle.get("name", "")}"> ')
                
                rack = cubicle.get('rack', {})
                xml_lines.append(f'\t\t\t<Rack id="{rack.get("id", "")}">')
                
                bp = rack.get('bp', {})
                xml_lines.append(f'\t\t\t\t<Bp id="{bp.get("id", "")}" size="{bp.get("size", "13")}" startSlot="{bp.get("startSlot", "1")}">')

                # Ordenar slots por número
                slots = bp.get('slots', {})
                sorted_slots = sorted(slots.items(), key=lambda x: int(x[0]))

                for slot_id, slot in sorted_slots:
                    slot_type = slot.get('type', 'EmptySlot')
                    slot_xml_id = slot.get('id', '')
                    
                    if slot_type == 'Psc':
                        xml_lines.append(f'\t\t\t\t\t<Psc id="{slot_xml_id}" slotId="{slot_id}" />')
                    
                    elif slot_type == 'Com':
                        attributes = [
                            f'id="{slot_xml_id}"',
                            f'canId="{slot.get("canId", "")}"',
                            f'type="COM_FSE"',
                            f'redundant="NORMAL"',
                            f'name="{slot.get("name", "")}"',
                            f'slotId="{slot_id}"'
                        ]
                        xml_lines.append(f'\t\t\t\t\t<Com {" ".join(attributes)}>')
                        xml_lines.append('\t\t\t\t\t</Com>')
                    
                    elif slot_type == 'Aeb':
                        attributes = [
                            f'id="{slot_xml_id}"',
                            f'name="{slot.get("name", "")}"',
                            f'canId="{slot.get("canId", "")}"',
                            f'refId="{slot.get("refId", "")}"',
                            f'slotId="{slot_id}"'
                        ]
                        xml_lines.append(f'\t\t\t\t\t<Aeb {" ".join(attributes)} />')
                    
                    elif slot_type == 'IoExb':
                        attributes = [
                            f'id="{slot_xml_id}"',
                            f'name="IO-EXB"',
                            f'refId="{slot.get("refId", "")}"',
                            f'slotId="{slot_id}"',
                        ]
                        if self.fds_model == "FDS102":
                            xml_lines.append(f'\t\t\t\t\t<IoExb {" ".join(attributes)}>')
                            fma0 = f'3{slot_xml_id[1:]}'
                            fma1 = f'4{slot_xml_id[1:]}'
                            xml_lines.append(f'\t\t\t\t\t\t<TrackSectionExtern>')
                            xml_lines.append(f'\t\t\t\t\t\t\t<FmaExtern refId={fma0}/>')
                            xml_lines.append(f'\t\t\t\t\t\t\t<FmaExtern refId={fma1}/>')
                            xml_lines.append(f'\t\t\t\t\t\t</TrackSectionExtern>')
                            xml_lines.append(f'\t\t\t\t\t</IoExb>')
                        else:
                            xml_lines.append(f'\t\t\t\t\t<IoExb {" ".join(attributes)} />')
                    
                    elif slot_type == 'EmptySlot':
                        xml_lines.append(f'\t\t\t\t\t<EmptySlot id="{slot_xml_id}" slotId="{slot_id}" />')
                
                xml_lines.append('\t\t\t\t</Bp>')
                xml_lines.append('\t\t\t</Rack>')
                xml_lines.append('\t\t</Cubicle>')
            
            xml_lines.append('\t</Cubicles>')
            
            xml_content = '\n'.join(xml_lines)
            
            self.xml_preview_text.delete(1.0, tk.END)
            self.xml_preview_text.insert(tk.END, xml_content)
            
            messagebox.showinfo("Sucesso", f"XML gerado para {len(self.cubicles_data)} cubículos!")
            
        except Exception as e:
            self.xml_preview_text.delete(1.0, tk.END)
            self.xml_preview_text.insert(tk.END, f"Erro ao gerar XML: {str(e)}")

    def save_cubicle_xml(self):
        """Salva o XML do cubicle em arquivo"""
        xml_content = self.xml_preview_text.get(1.0, tk.END).strip()
        if not xml_content or xml_content == "Nenhum cubicle selecionado.":
            messagebox.showwarning("Aviso", "Gere o XML primeiro.")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Salvar XML do Cubicle",
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            initialfile='Trackplan.xml'
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                messagebox.showinfo("Sucesso", f"XML salvo em: {filename}")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar arquivo: {str(e)}")

    def setup_rack_keyboard_navigation(self):
        """Configura navegação por teclado no canvas do rack"""
        try:
            # Tornar o canvas focável
            self.rack_canvas.focus_set()
            
            # Bind para navegação com setas
            self.rack_canvas.bind("<Left>", lambda event: self.navigate_slot(event, side='LEFT'))
            self.rack_canvas.bind("<Right>", lambda event: self.navigate_slot(event, side='RIGHT'))
            self.rack_canvas.bind("<Home>", self.scroll_rack_home)
            self.rack_canvas.bind("<End>", self.scroll_rack_end)
            
            # Bind para wheel do mouse
            self.rack_canvas.bind("<MouseWheel>", self.on_rack_mouse_wheel)

            # Bind para navegação com Enter
            self.rack_canvas.bind("<Return>", lambda event: self.slot_type_combo.focus_set())
            
        except Exception as e:
            print(f"Erro ao configurar navegação do rack: {e}")
        
    def navigate_slot(self, event, side='RIGHT'):
        """Navega para o slot anterior (esquerda)"""
        try:
            if not self.selected_slot:
                # Se nenhum slot selecionado, selecionar o primeiro
                if self.rack_slots:
                    self.select_slot_by_number(1)
                return
            
            current_slot_num = int(self.selected_slot)

            if side == 'RIGHT':
                next_slot_num = current_slot_num + 1
                # Verificar se existe slot anterior
                if str(next_slot_num) in self.rack_slots:
                    self.select_slot_by_number(next_slot_num)
                    # Scroll para garantir que o slot está visível
                    self.scroll_to_slot(next_slot_num)
            elif side == 'LEFT':
                previous_slot_num = current_slot_num - 1
                if str(previous_slot_num) in self.rack_slots:
                    self.select_slot_by_number(previous_slot_num)
                    # Scroll para garantir que o slot está visível
                    self.scroll_to_slot(previous_slot_num)

            else:
                print(f"ℹNão há slot para essa direção após: {current_slot_num}")
                    
        except Exception as e:
            print(f"Erro ao navegar para o proximo slot: {e}")

    def select_slot_by_number(self, slot_number):
        """Seleciona um slot pelo seu número"""
        try:
            slot_id = str(slot_number)
            
            if slot_id not in self.rack_slots:
                print(f"Slot {slot_number} não existe")
                return
            
            # Atualizar slot selecionado
            self.selected_slot = slot_id
            self.selected_slot_var.set(f"Slot {slot_id}")
            
            # Carregar propriedades do slot
            self.load_slot_properties()
            
            # Redesenhar rack para mostrar seleção
            self.draw_rack_layout()
            
            # Focar no canvas para receber próximas teclas
            self.rack_canvas.focus_set()
                        
        except Exception as e:
            print(f"Erro ao selecionar slot {slot_number}: {e}")

    def scroll_to_slot(self, slot_number):
        """Faz scroll automático para garantir que o slot está visível"""
        try:
            # Calcular posição do slot
            slot_width = 40
            spacing = 5
            margin = 20
            
            slot_x_start = margin + (slot_number - 1) * (slot_width + spacing)
            slot_x_end = slot_x_start + slot_width
            
            # Obter dimensões visíveis do canvas
            canvas_width = self.rack_canvas.winfo_width()
            
            # Obter scroll atual
            x_view = self.rack_canvas.xview()
            total_width = float(self.rack_canvas.cget("scrollregion").split()[2])
            
            visible_start = x_view[0] * total_width
            visible_end = x_view[1] * total_width
            
            # Verificar se slot está visível
            if slot_x_start < visible_start:
                # Slot está à esquerda da área visível - scroll para a esquerda
                new_x = max(0, slot_x_start - margin) / total_width
                self.rack_canvas.xview_moveto(new_x)
                
            elif slot_x_end > visible_end:
                # Slot está à direita da área visível - scroll para a direita
                new_x = min(1, (slot_x_end - canvas_width + margin) / total_width)
                self.rack_canvas.xview_moveto(new_x)
            else:
                # Slot já está visível  
                pass                
        except Exception as e:
            print(f"Erro ao fazer scroll para slot {slot_number}: {e}")

    def open_fma_editor(self):
        """Abre o editor de FMA para elementos selecionados"""
        # Filtrar apenas FMAs (ignorar células vazias que são tuplas)
        fma_elements = [elem for elem in self.selected_elements 
                       if isinstance(elem, dict) and elem.get('type') == 'fma']
        
        if not fma_elements:
            messagebox.showwarning("Aviso", "Selecione uma FMA para editar.")
            return
        
        if len(fma_elements) > 1:
            messagebox.showwarning("Aviso", "Selecione apenas uma FMA por vez para edição.")
            return
        
        # Fechar janela anterior se existir
        if self.fma_config_window and self.fma_config_window.winfo_exists():
            self.fma_config_window.destroy()
        
        # Armazenar referência da FMA atual
        self.current_fma_element = fma_elements[0]
        
        # Criar nova janela de configuração
        self.create_fma_config_window()
    
    def refresh_fma_test_window(self):
        """Atualiza as listas do Finder (FMAs/Sensores) se a janela estiver aberta."""
        try:
            if not getattr(self, 'fma_test_window', None) or not self.fma_test_window.winfo_exists():
                return

            nb = getattr(self, '_fma_test_notebook', None)
            tree_fma = getattr(self, '_fma_test_tree_fma', None)
            tree_sensor = getattr(self, '_fma_test_tree_sensor', None)
            if not nb or not tree_fma or not tree_sensor:
                return

            filter_var = getattr(self, '_fma_test_filter_var', None)
            search = (filter_var.get() if filter_var else "").strip().lower()

            # Recriar listas a partir do estado atual
            fmas = [e for e in getattr(self, 'trackplan_elements', []) if isinstance(e, dict) and e.get('type') == 'fma']
            sensors = [e for e in getattr(self, 'trackplan_elements', []) if isinstance(e, dict) and e.get('type') == 'sensor']

            # Atualizar tree de FMAs
            tree_fma.delete(*tree_fma.get_children())
            for fma in fmas:
                fid = str(fma.get('id', ''))
                name = (fma.get('name', '') or '')
                x = fma.get('x', 0)
                y = fma.get('y', 0)

                if search and (search not in fid.lower()) and (search not in name.lower()) and (search not in f"({x}, {y})".lower()):
                    continue

                try:
                    tree_fma.insert("", tk.END, iid=fid, values=(fid, name, f"({x}, {y})"))
                except Exception:
                    tree_fma.insert("", tk.END, values=(fid, name, f"({x}, {y})"))

            # Atualizar tree de Sensores
            tree_sensor.delete(*tree_sensor.get_children())
            for s in sensors:
                sid = str(s.get('id', ''))
                name = (s.get('name', '') or '')
                x = s.get('x', 0)
                y = s.get('y', 0)
                has_fma = bool(s.get('fma0')) or bool(s.get('fma1'))
                fma_status = "✓ Sim" if has_fma else "✗ Não"

                if search and (search not in sid.lower()) and (search not in name.lower()) and (search not in fma_status.lower()):
                    continue

                try:
                    tree_sensor.insert("", tk.END, iid=sid, values=(sid, name, f"({x}, {y})", fma_status))
                except Exception:
                    tree_sensor.insert("", tk.END, values=(sid, name, f"({x}, {y})", fma_status))

        except Exception as e:
            print(f"refresh_fma_test_window: {e}")

    def open_fma_test(self):
        """ Cria janela de testes para as FMAs e Sensores"""
        if getattr(self, 'fma_test_window', None) and self.fma_test_window.winfo_exists():
            self.fma_test_window.lift()
            self.fma_test_window.focus_force()
            return
        
        self.fma_test_window = tk.Toplevel(self.root)
        self.fma_test_window.title(f"Finder")
        self.fma_test_window.geometry("460x350")
        self.fma_test_window.transient(self.root)
        self.fma_test_window.resizable(False, False)

        self.fma_test_window.protocol("WM_DELETE_WINDOW", self.close_fma_test)

        self.fma_test_window.columnconfigure(0, weight=2)
        self.fma_test_window.columnconfigure(1, weight=1)

        notebook_test = ttk.Notebook(self.fma_test_window)
        notebook_test.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        basic_tab_frame = ttk.Frame(notebook_test)
        notebook_test.add(basic_tab_frame, text="Lista de FMAs")

        # Configurar grid do rfame interno
        basic_tab_frame.rowconfigure(0, weight=1)
        basic_tab_frame.columnconfigure(0, weight=1)

        fma_elements = [elem for elem in getattr(self, 'trackplan_elements', [])
            if isinstance(elem, dict) and elem.get('type') == 'fma']

        # Tree para listar FMAs
        tree = ttk.Treeview(basic_tab_frame, columns=('ID', 'Nome', 'Posição'), show='headings', height=12)
        tree.heading('ID', text='ID')
        tree.heading('Nome', text='Nome')
        tree.heading('Posição', text='Posição (x,y)')
        tree.column('ID', width=90, anchor='center')
        tree.column('Nome', width=120, anchor='w')
        tree.column('Posição', width=120, anchor='center')

        vs = ttk.Scrollbar(basic_tab_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        if fma_elements:
            for fma in fma_elements:
                getter = getattr(fma, "get", None)
                if callable(getter):
                    fid = getter("id", "")
                    name = getter("name", "")
                    x = getter("x", "?")
                    y = getter("y", "?")
                else:
                    fid = getattr(fma, "id", "")
                    name = getattr(fma, "name", "")
                    x = getattr(fma, "x", "?")
                    y = getattr(fma, "y", "?")
                pos_text = f"({x}, {y})"
                tree.insert("", tk.END, values=(fid, name, pos_text))

        tree.grid(row=0, column=0, sticky="nsew", )
        vs.grid(row=0, column=1, sticky="ns")

        sensor_finder_frame = ttk.Frame(notebook_test)
        notebook_test.add(sensor_finder_frame, text="Lista de sensores")
        
        sensor_elements = [elem for elem in getattr(self, 'trackplan_elements', [])
            if isinstance(elem, dict) and elem.get('type') == 'sensor']

        # Tree para listar sensores
        tree_sensor = ttk.Treeview(sensor_finder_frame, columns=('ID', 'Nome', 'Posição', 'FMA'), show='headings', height=12)
        tree_sensor.heading('ID', text='ID')
        tree_sensor.heading('Nome', text='Nome')
        tree_sensor.heading('Posição', text='Posição (x,y)')
        tree_sensor.heading('FMA', text='Possui FMA')
        tree_sensor.column('ID', width=90, anchor='center')
        tree_sensor.column('Nome', width=120, anchor='w')
        tree_sensor.column('Posição', width=120, anchor='center')
        tree_sensor.column('FMA', width=80, anchor='center')

        vs = ttk.Scrollbar(sensor_finder_frame, orient="vertical", command=tree_sensor.yview)
        tree_sensor.configure(yscrollcommand=vs.set)
        if sensor_elements:
            for sensor in sensor_elements:
                sid = str(sensor.get('id', ''))
                name = sensor.get('name', '') or ''
                x = sensor.get('x', 0)
                y = sensor.get('y', 0)
                
                # Verificar se sensor possui FMA (fma0 e fma1)
                fma1 = bool(sensor.get('fma0'))
                fma2 = bool(sensor.get('fma1'))
                has_fma = fma1 or fma2
                fma_status = "✓ Sim" if has_fma else "✗ Não"
                
                tree_sensor.insert("", tk.END, iid=sid, values=(sid, name, f"({x}, {y})", fma_status))

        tree_sensor.grid(row=0, column=0, sticky="nsew", )
        vs.grid(row=0, column=1, sticky="ns")

        # Configurar grid do frame interno
        sensor_finder_frame.rowconfigure(0, weight=1)
        sensor_finder_frame.columnconfigure(0, weight=1)

        def on_item_click(event):
            """Seleciona a FMA na TreeView, limpa seleção anterior e destaca no canvas."""
            try:
                sel = tree.selection()
                item = sel[0] if sel else tree.focus()
                if not item:
                    return
                
                # ID da FMA
                fma_id = tree.item(sel)['values'][0]
                # Procurar FMA correspondente
                fma = None
                for elem in getattr(self, 'trackplan_elements', []):
                    if isinstance(elem, dict) and elem.get('type') == 'fma' and str(elem.get('id', '')) == str(fma_id):
                        fma = elem
                        break

                if not fma:
                    messagebox.showwarning("Aviso", f"FMA com ID {fma_id} não encontrada.")
                    return

                # limpar destaques e seleção anteriores
                try:
                    self.clear_all_highlights()
                except Exception:
                    pass
                try:
                    self.clear_selection()
                except Exception:
                    pass

                # atualizar FMA atual, selecionar e destacar
                self.current_fma_element = fma
                try:
                    self.select_element(fma)  # mantém lista de selecionados coerente
                except Exception:
                    pass

                # foco no canvas para feedback
                try:
                    self.trackplan_canvas.focus_set()
                except Exception:
                    pass

                # Destacar e mover scroll para o elemento
                self.highlight_element(self.current_fma_element, temporary=False, color="darkblue")
                self.scroll_to_element(self.current_fma_element)

                # feedback no título
                fname = self.current_fma_element.get('name', '')
                fx = self.current_fma_element.get('x', 0)
                fy = self.current_fma_element.get('y', 0)
                self.fma_test_window.title(f"Testando FMAs - Selecionada: {fname} [{fma_id}] ({fx},{fy})")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao selecionar FMA: {e}")

        tree.bind("<<TreeviewSelect>>", on_item_click)
        tree.bind("<Double-1>", on_item_click)

        def on_sensor_item_click(event):
            """Seleciona o Sensor na TreeView, limpa seleção anterior e destaca no canvas."""
            try:
                selected = tree_sensor.selection()
                if not selected:
                    return
                
                item_values = tree_sensor.item(selected[0], 'values')
                if not item_values or len(item_values) < 1:
                    return
                
                sensor_id_str = str(item_values[0]).strip()  # ID está na primeira coluna
                
                if not sensor_id_str:
                    return
                                
                # Limpar seleção anterior
                self.clear_selection()
                try:
                    self.clear_all_highlights()
                except Exception:
                    pass
                
                # Buscar o sensor na lista de elementos
                sensor_found = None
                for element in self.trackplan_elements:
                    if element.get('type') == 'sensor':
                        elem_id = str(element.get('id', '')).strip()                        
                        if elem_id == sensor_id_str:
                            sensor_found = element
                            break
                
                if sensor_found:                    
                    # Selecionar o sensor
                    self.select_element(sensor_found)
                    self.update_selection_info()
                    
                    # Fazer scroll até o sensor no canvas
                    self.scroll_to_element(sensor_found, center=True)
                    
                    # Focar o canvas
                    self.trackplan_canvas.focus_set()
                    
                else:
                    print(f"❌ Sensor ID '{sensor_id_str}' não encontrado na lista de elementos")
                    messagebox.showwarning("Sensor não encontrado", 
                                        f"Sensor com ID '{sensor_id_str}' não existe no trackplan.")
                    
            except Exception as e:
                print(f"❌ Erro ao selecionar sensor: {e}")
                traceback.print_exc()

        tree_sensor.bind("<<TreeviewSelect>>", on_sensor_item_click)
        tree_sensor.bind("<Double-1>", on_sensor_item_click)

        # Guardar refs para poder atualizar
        self._fma_test_notebook = notebook_test
        self._fma_test_tree_fma = tree
        self._fma_test_tree_sensor = tree_sensor

        ttk.Button(self.fma_test_window, text="Testar FMA", command=self.test_fma_highlights).grid(row=1, column=0, pady=10, padx=10, sticky='nw')
        ttk.Label(self.fma_test_window, text="Pesquisar:").grid(row=1, column=0, pady=10)

        # Manter StringVar em self e NÃO perder referência do Entry (grid separado)
        self._fma_test_filter_var = tk.StringVar()
        filter_entry = ttk.Entry(self.fma_test_window, textvariable=self._fma_test_filter_var, width=20)
        filter_entry.grid(row=1, column=0, pady=10, padx=10, sticky='ne')

        # Atualiza ao digitar e ao trocar aba
        self._fma_test_filter_var.trace_add("write", lambda *_: self.refresh_fma_test_window())
        notebook_test.bind("<<NotebookTabChanged>>", lambda e: self.refresh_fma_test_window())

        # Primeira carga
        self.refresh_fma_test_window()

        def apply_filter(*args):
            current = notebook_test.select()
            if current == str(basic_tab_frame):
                search_term = (self._fma_test_filter_var.get() or "").strip().lower()
                tree.delete(*tree.get_children())
                for fma in fma_elements:
                    fid = str(fma.get('id', ''))
                    name = (fma.get('name', '') or '')
                    x = fma.get('x', 0)
                    y = fma.get('y', 0)
                    # match por ID ou Nome
                    if not search_term or (search_term in fid.lower() or search_term in name.lower()):
                        tree.insert("", tk.END, iid=fid, values=(fid, name, f"({x}, {y})"))
            elif current == str(sensor_finder_frame):
                search_term = (self._fma_test_filter_var.get() or "").strip().lower()
                tree_sensor.delete(*tree_sensor.get_children())
                for sensor in sensor_elements:
                    sid = str(sensor.get('id', ''))
                    name = (sensor.get('name', '') or '')
                    x = sensor.get('x', 0)
                    y = sensor.get('y', 0)
                    
                    # Verificar se sensor possui FMA
                    has_fma = bool(sensor.get('fma0')) or bool(sensor.get('fma1'))
                    fma_status = "✓ Sim" if has_fma else "✗ Não"
                    
                    # Match por ID, Nome ou Status de FMA
                    if not search_term or (search_term in sid.lower() or 
                                        search_term in name.lower() or 
                                        search_term in fma_status.lower()):
                        tree_sensor.insert("", tk.END, iid=sid, values=(sid, name, f"({x}, {y})", fma_status))

        self._fma_test_filter_var.trace_add("write", apply_filter)

    def scroll_to_element(self, element, center=True, pad_cells=1):
        """Faz scroll no trackplan_canvas para mostrar/centralizar o elemento."""
        try:
            if not hasattr(self, 'trackplan_canvas') or not self.trackplan_canvas:
                return
            # posição do elemento em células
            ex = int(element.get('x', 0))
            ey = int(element.get('y', 0))

            # converter para coordenadas em pixels (canto superior esquerdo da célula)
            cell = self.grid_size
            target_x = (ex + 1) * cell
            target_y = (ey + 1) * cell

            # dimensões visíveis do canvas
            self.trackplan_canvas.update_idletasks()
            view_w = self.trackplan_canvas.winfo_width()
            view_h = self.trackplan_canvas.winfo_height()

            # scrollregion total
            sr = self.trackplan_canvas.cget("scrollregion")
            if not sr:
                return
            x0, y0, x1, y1 = map(int, sr.split())

            # calcular destino (centralizar ou garantir visibilidade com padding)
            if center:
                dest_x = max(x0, min(target_x - view_w // 2, x1 - view_w))
                dest_y = max(y0, min(target_y - view_h // 2, y1 - view_h))
            else:
                pad = pad_cells * cell
                left = max(x0, target_x - pad)
                top = max(y0, target_y - pad)
                dest_x = min(left, x1 - view_w)
                dest_y = min(top, y1 - view_h)

            # normalizar para [0..1] para moveto
            x_frac = 0.0 if (x1 - x0) <= 0 else (dest_x - x0) / (x1 - x0)
            y_frac = 0.0 if (y1 - y0) <= 0 else (dest_y - y0) / (y1 - y0)

            self.trackplan_canvas.xview_moveto(x_frac)
            self.trackplan_canvas.yview_moveto(y_frac)

            # focar canvas para navegação
            try:
                self.trackplan_canvas.focus_set()
            except Exception:
                pass
        except Exception as e:
            print(f"scroll_to_element erro: {e}")

    def close_fma_test(self):
        try:
            # limpar destaques e seleção ao fechar
            try:
                self.clear_all_highlights()
            except Exception:
                pass
            try:
                self.clear_selection()
            except Exception:
                pass

            if hasattr(self, 'fma_test_window') and self.fma_test_window:
                try:
                    self.fma_test_window.destroy()
                except Exception:
                    pass
            self.fma_test_window = None
            if hasattr(self, '_fma_test_tree'):
                self._fma_test_tree = None
        except Exception:
            pass

    def create_fma_config_window(self):
        """Cria janela de configuração completa para FMA"""
        self.fma_config_window = tk.Toplevel(self.root)
        self.fma_config_window.title(f"Configuração FMA - {self.current_fma_element.get('name', 'Sem nome')}")
        self.fma_config_window.geometry("600x570")
        self.fma_config_window.transient(self.root)
        
        self.fma_config_window.protocol("WM_DELETE_WINDOW", self.close_fma_config)

        # Notebook para organizar as abas
        notebook = ttk.Notebook(self.fma_config_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # === ABA 1: DADOS BÁSICOS ===
        basic_tab = ttk.Frame(notebook)
        notebook.add(basic_tab, text="Dados Básicos")
        
        basic_frame = ttk.LabelFrame(basic_tab, text="Informações da FMA", padding="10")
        basic_frame.pack(fill=tk.X, padx=10, pady=10)

        # === FRAME PARA TIPO DE FMA ===
        fma_type_frame = ttk.Frame(basic_frame)
        fma_type_frame.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
    
        # Variável para controlar o tipo de FMA
        self.fma_type_var = tk.BooleanVar()

        # Determinar tipo atual baseado no ID existente
        current_id = str(self.current_fma_element.get('id', ''))
        if current_id.startswith('3'):
            self.fma_type_var.set(True)  # FMA1
        elif current_id.startswith('4'):
            self.fma_type_var.set(False)  # FMA2
        else:
            self.fma_type_var.set(True)  # Padrão FMA1
        
        # Radio buttons para tipo de FMA
        ttk.Label(fma_type_frame, text="Tipo de FMA:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        fma1_radio = ttk.Radiobutton(fma_type_frame, text="FMA1 (prefixo 3)", 
                                    variable=self.fma_type_var, value=True,
                                    command=self.on_fma_type_change)
        fma1_radio.pack(side=tk.LEFT, padx=(0, 15))
        
        fma2_radio = ttk.Radiobutton(fma_type_frame, text="FMA2 (prefixo 4)", 
                                    variable=self.fma_type_var, value=False,
                                    command=self.on_fma_type_change)
        fma2_radio.pack(side=tk.LEFT)

        # Id da FMA
        row = 1
        ttk.Label(basic_frame, text="ID da FMA:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.fma_id_var = tk.StringVar(value=str(self.current_fma_element.get('id', '')))
        fma_id_entry = ttk.Entry(basic_frame, textvariable=self.fma_id_var, width=15)
        fma_id_entry.grid(row=row, column=1, sticky="w", padx=10, pady=5)

        self.fma_id_var.trace_add('write', self.update_fma_auto_fields)

        # Nome da FMA
        row += 1
        ttk.Label(basic_frame, text="Nome da FMA:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.fma_name_var = tk.StringVar(value=self.current_fma_element.get('name', ''))
        name_entry = ttk.Entry(basic_frame, textvariable=self.fma_name_var, width=15)
        name_entry.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        
        self.fma_name_var.trace_add('write', self.update_fma_auto_fields)
        # Ângulo da FMA
        row += 1
        ttk.Label(basic_frame, text="Ângulo:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.fma_angle_var = tk.StringVar(value=str(self.current_fma_element.get('angle', '0')))
        angle_combo = ttk.Combobox(basic_frame, textvariable=self.fma_angle_var, values=['0', '90', '180', '270'], width=10, state="readonly")
        angle_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        # Atualizar ângulo em tempo real
        self.fma_angle_var.trace_add('write', self.update_fma_angle_on_canvas)
        
        # Posição (somente leitura)
        row += 1
        ttk.Label(basic_frame, text="Posição (x, y):", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        pos_text = f"({self.current_fma_element.get('x', '?')}, {self.current_fma_element.get('y', '?')})"
        ttk.Label(basic_frame, text=pos_text, foreground="blue").grid(row=row, column=1, sticky="w", padx=10, pady=5)
        
        # RefIde="readonly", foreground="gray"
        row += 1
        ttk.Label(basic_frame, text="Ref ID:", font=("Arial", 9, "bold")).grid(row=row, column=0, sticky="w", pady=5)
        self.fma_ref_id_var = tk.StringVar(value=self.current_fma_element.get('ref_id', ''))
        ref_id_entry = ttk.Entry(basic_frame, textvariable=self.fma_ref_id_var, width=15,
                                state="readonly", foreground="gray")
        ref_id_entry.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        
        # === ABA 2: SENSORES ===
        sensors_tab = ttk.Frame(notebook)
        notebook.add(sensors_tab, text="Sensores Associados")
        
        sensors_frame = ttk.LabelFrame(sensors_tab, text="Sensores da FMA", padding="10")
        sensors_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Lista de sensores atuais
        ttk.Label(sensors_frame, text="Sensores associados:", font=("Arial", 9, "bold")).pack(anchor="w")
        
        list_frame = ttk.Frame(sensors_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.sensors_listbox = tk.Listbox(list_frame, height=10)
        sensors_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.sensors_listbox.yview)
        self.sensors_listbox.configure(yscrollcommand=sensors_scrollbar.set)
        self.sensors_listbox.pack(side="left", fill="both", expand=True)
        sensors_scrollbar.pack(side="right", fill="y")
        
        # Botões para sensores
        sensors_buttons = ttk.Frame(sensors_frame)
        sensors_buttons.pack(fill=tk.X, pady=10)
        
        ttk.Button(sensors_buttons, text="➕ Adicionar Sensor", command=self.add_sensor_to_fma).pack(side=tk.LEFT, padx=5)
        ttk.Button(sensors_buttons, text="➖ Remover Sensor", command=self.remove_sensor_from_fma).pack(side=tk.LEFT, padx=5)
        ttk.Button(sensors_buttons, text="Destacar no Canvas", command=self.highlight_selected_sensor).pack(side=tk.LEFT, padx=5)
        
        # === ABA 3: TRILHOS ===
        rails_tab = ttk.Frame(notebook)
        notebook.add(rails_tab, text="Trilhos Associados")
        
        rails_frame = ttk.LabelFrame(rails_tab, text="Trilhos da FMA", padding="10")
        rails_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Lista de trilhos atuais
        ttk.Label(rails_frame, text="Trilhos associados:", font=("Arial", 9, "bold")).pack(anchor="w")
        
        rails_list_frame = ttk.Frame(rails_frame)
        rails_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.rails_listbox = tk.Listbox(rails_list_frame, height=10)
        rails_scrollbar = ttk.Scrollbar(rails_list_frame, orient="vertical", command=self.rails_listbox.yview)
        self.rails_listbox.configure(yscrollcommand=rails_scrollbar.set)
        self.rails_listbox.pack(side="left", fill="both", expand=True)
        rails_scrollbar.pack(side="right", fill="y")
        
        # Botões para trilhos
        rails_buttons = ttk.Frame(rails_frame)
        rails_buttons.pack(fill=tk.X, pady=10)
        
        # Botão legado removido: adição de trilho individual substituída por seleção múltipla
        ttk.Button(rails_buttons, text="➖ Remover Trilho", command=self.remove_rail_from_fma).pack(side=tk.LEFT, padx=5)
        ttk.Button(rails_buttons, text="Destacar no Canvas", command=self.highlight_selected_rail).pack(side=tk.LEFT, padx=5)

        # Seleção múltipla no canvas (rails/switch/link/crossing)
        ttk.Button(rails_buttons, text="Selecionar Trilhos/Chaves/Links/Cruzamentos…",
               command=self.start_fma_multi_pick_mode).pack(side=tk.LEFT, padx=10)

        # Info de seleção
        self._fma_pick_info_var = tk.StringVar(value="Seleção inativa (Enter confirma, Esc cancela)")
        ttk.Label(rails_frame, textvariable=self._fma_pick_info_var, foreground="gray").pack(anchor="w")
        
        # === BOTÕES FINAIS ===
        buttons_frame = ttk.Frame(self.fma_config_window)
        buttons_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(buttons_frame, text="Testar FMA (Destacar Limites)", 
                  command=self.test_fma_highlights, 
                  style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Limpar Destaques", 
                  command=self.clear_all_highlights).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Salvar", 
                  command=self.save_fma_config).pack(side=tk.RIGHT, padx=5)
        ttk.Button(buttons_frame, text="Cancelar", 
                  command=self.close_fma_config).pack(side=tk.RIGHT, padx=5)
        
        # Carregar dados atuais
        self.load_fma_config_data()

        # Bind de teclas para confirmar/cancelar no modo de seleção
        try:
            self.fma_config_window.bind("<Return>", lambda e: self._fma_pick_confirm())
            self.fma_config_window.bind("<Escape>", lambda e: self._fma_pick_cancel())
        except Exception:
            pass

    def on_fma_type_change(self):
        """Chamado quando o tipo de FMA muda (FMA1/FMA2)"""
        # Forçar atualização dos campos baseado no novo tipo
        self.update_fma_auto_fields_with_type()

    def update_fma_auto_fields_with_type(self, *args):
        """Wrapper para update_fma_auto_fields que considera o tipo de FMA"""
        self.update_fma_auto_fields()

    def update_fma_name_on_canvas(self, fma_name):
        """Atualiza o nome da FMA no canvas em tempo real"""
        if not self.current_fma_element:
            return

        new_name = fma_name if fma_name else self.fma_name_var.get()
        self.current_fma_element['name'] = new_name
        
        # Regenerar a imagem da FMA com o novo nome
        self.redraw_fma_element(self.current_fma_element)
    
    def update_fma_angle_on_canvas(self, *args):
        """Atualiza o ângulo da FMA no canvas em tempo real"""
        if not self.current_fma_element:
            return
        
        new_angle = int(self.fma_angle_var.get())
        self.current_fma_element['angle'] = new_angle
        
        # Regenerar a imagem da FMA com o novo ângulo
        self.redraw_fma_element(self.current_fma_element)
    
    def redraw_fma_element(self, fma_element):
        """Redesenha um elemento FMA no canvas"""
        if not fma_element or 'id' not in fma_element:
            return
        
        # Remover elemento visual antigo do canvas
        if 'canvas_id' in fma_element:
            self.trackplan_canvas.delete(fma_element['canvas_id'])
        
        # Gerar nova imagem com texto integrado
        element_image = self.create_fma_image_with_integrated_text(
            fma_element.get('angle', 0),
            fma_element.get('name', '')
        )
        
        if not element_image:
            print(f"Erro ao gerar imagem da FMA {fma_element.get('name', 'sem nome')}")
            return
        
        # Usar as coordenadas corretas do canvas (já convertidas quando o elemento foi criado)
        grid_x, grid_y = fma_element.get('x', 0), fma_element.get('y', 0)
        canvas_x = grid_x * self.grid_size + self.grid_size
        canvas_y = grid_y * self.grid_size + self.grid_size
        canvas_id = self.trackplan_canvas.create_image(canvas_x, canvas_y, image=element_image, anchor='nw')
        
        # Atualizar referências
        fma_element['canvas_id'] = canvas_id
        
        # Inicializar element_images se não existir
        if not hasattr(self, 'element_images'):
            self.element_images = {}
        
        # Armazenar imagem para evitar garbage collection
        self.element_images[canvas_id] = element_image
        
        # Também armazenar na própria FMA para garantir
        fma_element['current_image'] = element_image
            
    def load_fma_config_data(self):
        """Carrega os dados atuais da FMA nas listas"""
        if not self.current_fma_element:
            return
        
        # Carregar sensores
        self.sensors_listbox.delete(0, tk.END)
        for sensor in self.current_fma_element.get('associated_sensors', []):
            sensor_id = sensor.get('refId', 'N/A')
            position = sensor.get('fmaPosition', 'center')
            self.sensors_listbox.insert(tk.END, f"{sensor_id} ({position})")
        
        # Carregar trilhos
        self.rails_listbox.delete(0, tk.END)
        for rail in self.current_fma_element.get('associated_rails', []):
            rail_id = rail.get('refId', 'N/A')
            self.rails_listbox.insert(tk.END, rail_id)
    
    def add_sensor_to_fma(self):
        if not self.current_fma_element:
            messagebox.showwarning("Aviso", "Nenhuma FMA selecionada.")
            return

        messagebox.showinfo(
            "Info",
            "Clique no canvas em um sensor para adicioná-lo à FMA.\n"
            "A posição será sugerida automaticamente."
        )
        self.fma_config_window.withdraw()

        fma_x = int(self.current_fma_element.get('x', 0))
        fma_y = int(self.current_fma_element.get('y', 0))

        self.trackplan_canvas.bind(
            "<Button-1>",
            lambda event: self.select_sensor_for_fma(event, fma_x, fma_y)
        )
    def select_sensor_for_fma(self, event, fma_x, fma_y):
        try:
            """Seleciona sensor clicado para adicionar à FMA"""
            # Converter coordenadas
            canvas_x = self.trackplan_canvas.canvasx(event.x)
            canvas_y = self.trackplan_canvas.canvasy(event.y)
            grid_x = int((canvas_x - self.grid_size) // self.grid_size) # coordenada x do sensor
            grid_y = int((canvas_y - self.grid_size) // self.grid_size) # coordenada y do sensor
            sensor_angle = int(self.current_fma_element.get('angle', 0))

            # Seleciona posição visualmente
            self.select_position(grid_x, grid_y)

            # Procurar sensor na posição
            sensor_element = None
            for element in self.trackplan_elements:
                if element.get('type') == 'sensor' and element.get('x') == grid_x and element.get('y') == grid_y:
                    sensor_element = element
                    break

            self.fma_config_window.deiconify()  # Restaurar janela
            self.clear_selection()
            if not sensor_element:
                messagebox.showwarning("Aviso", "Nenhum sensor encontrado na posição clicada.")
                return
            
            # Evitar duplicado
            sensor_id = str(sensor_element.get('id', ''))
            existing_sensors = self.current_fma_element.get('associated_sensors', [])
            if any(s.get('refId') == sensor_id for s in existing_sensors):
                messagebox.showwarning("Sensor já adicionado", f"O sensor {sensor_id} já está associado a esta FMA.")
                return

            # Usar nova interface visual para escolher posição do sensor
            position = self.show_sensor_position_dialog(sensor_element, grid_x, fma_x, fma_y, grid_y, sensor_angle)
            
            if not position:
                return  # Usuário cancelou

            # Adicionar sensor à FMA
            sensor_data = {
                'refId': str(sensor_element.get('id', '')),
                'fmaPosition': position
            }

            if 'associated_sensors' not in self.current_fma_element:
                self.current_fma_element['associated_sensors'] = []
            self.current_fma_element['associated_sensors'].append(sensor_data)
            self.sensors_listbox.insert(tk.END, f"{sensor_data['refId']} ({position})")
            messagebox.showinfo("Sucesso", f"Sensor {sensor_data['refId']} adicionado com posição '{position}'.")
        finally:
            # Sempre restaurar bindings e foco do canvas
            self.trackplan_canvas.unbind("<Button-1>")
            self.restore_canvas_bindings()

    def remove_sensor_from_fma(self):
        """Remove sensor selecionado da FMA"""
        selection = self.sensors_listbox.curselection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um sensor para remover.")
            return
        
        index = selection[0]
        self.sensors_listbox.delete(index)
        
        # Remover do elemento também
        if 'associated_sensors' in self.current_fma_element and index < len(self.current_fma_element['associated_sensors']):
            del self.current_fma_element['associated_sensors'][index]
    
    def show_sensor_position_dialog(self, sensor_element, grid_x, grid_x_fma, grid_y_fma, grid_y, sensor_angle):
        """Mostra diálogo visual para escolher posição do sensor com preview"""
        # Criar janela de diálogo
        dialog = tk.Toplevel(self.root)
        dialog.title("Posicionamento do Sensor na FMA")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Centralizar janela
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 250
        y = (dialog.winfo_screenheight() // 2) - 200
        dialog.geometry(f"700x600+{x}+{y}")
        
        # Variável para armazenar resultado
        result = {'position': None}

        default_pos = 'right' if grid_x < grid_x_fma else 'left'
        position_var = tk.StringVar(value=default_pos)
        
        # Frame principal
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Escolha a Posição do Sensor na FMA", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Informações do sensor
        info_frame = ttk.LabelFrame(main_frame, text="Sensor Selecionado", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        sensor_info = f"ID: {sensor_element.get('id', 'N/A')} | Ângulo: {sensor_element.get('angle', 0)}°"
        ttk.Label(info_frame, text=sensor_info, font=("Arial", 10)).pack()
        
        # Frame para opções de posição
        position_frame = ttk.LabelFrame(main_frame, text="Posicionamento", padding="15")
        position_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Radio buttons para posição
        ttk.Radiobutton(position_frame, text="🠐 Esquerda", variable=position_var, 
                       value='left', command=lambda: self.update_sensor_preview(preview_canvas, sensor_element, 'left')).pack(side=tk.LEFT, padx=20)
        ttk.Radiobutton(position_frame, text="🠒 Direita", variable=position_var, 
                       value='right', command=lambda: self.update_sensor_preview(preview_canvas, sensor_element, 'right')).pack(side=tk.RIGHT, padx=20)
        
        # Frame para preview
        preview_frame = ttk.LabelFrame(main_frame, text="Preview do Sensor Destacado", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Canvas para preview
        preview_canvas = tk.Canvas(preview_frame, bg="lightgray", width=400, height=150)
        preview_canvas.pack(pady=10)
        
        # Inicializar preview com posição dependendo da posição do sensor em relação a fma
        self.update_sensor_preview(preview_canvas, sensor_element, default_pos)
        
        # Frame para botões
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        def on_confirm():
            result['position'] = position_var.get()
            dialog.destroy()
        # Botões de ação
        confirm_btn = ttk.Button(button_frame, text="Confirmar", command=on_confirm)
        cancel_btn = ttk.Button(button_frame, text="Cancelar", command=lambda: (result.update({'position': None}), dialog.destroy()))
        confirm_btn.pack(side=tk.RIGHT, padx=5)
        cancel_btn.pack(side=tk.RIGHT, padx=5)

        # Aguardar fechamento da janela e retornar resultado
        dialog.wait_window(dialog)
        return result['position']
    
    def update_sensor_preview(self, canvas, sensor_element, position):
        """Atualiza o preview visual do sensor na posição escolhida usando imagens existentes"""
        # Limpeza no canvas
        canvas.delete("all")

        try:
            # Obter ângulo do sensor
            sensor_angle = sensor_element.get('angle', 0)
            direction_text = "Esquerda" if position == 'left' else "Direita"

            # Desenhar título
            canvas.create_text(200, 20, text=f"Sensor com destaque na {direction_text} (ângulo {sensor_angle}°)", 
                             font=("Arial", 12, "bold"))
            
            # Posição central do canvas para desenhar
            center_x, center_y = 200, 90
            
            # Carregar imagem azul existente diretamente
            try:
                from PIL import Image, ImageTk
                import os
                
                # Construir caminho para a imagem azul existente
                images_dir = os.path.join(os.path.dirname(__file__), "images", "blue")
                image_filename = f"sensor_{sensor_angle}_{position}.png"
                image_path = os.path.join(images_dir, image_filename)
                                
                # Verificar se arquivo existe e carregar
                if os.path.exists(image_path):
                    # Carregar imagem existente
                    pil_image = Image.open(image_path)
                    
                    # Redimensionar para melhor visualização no preview (aumentar 2x)
                    new_size = (pil_image.width * 2, pil_image.height * 2)
                    pil_image = pil_image.resize(new_size, Image.Resampling.NEAREST)
                    
                    # Converter para PhotoImage
                    sensor_image = ImageTk.PhotoImage(pil_image)
                    
                    # Desenhar sensor no canvas
                    canvas.create_image(center_x, center_y, image=sensor_image)
                    
                    # Armazenar referência para evitar garbage collection
                    if not hasattr(self, 'preview_images'):
                        self.preview_images = {}
                    self.preview_images[f"sensor_preview_{sensor_angle}_{position}"] = sensor_image
                else:
                    print(f"Imagem não encontrada: {image_filename}")
                    # Imagem não encontrada
                    canvas.create_text(center_x, center_y, 
                                     text=f"Imagem não encontrada:\n{image_filename}", 
                                     font=("Arial", 12), fill="red", justify="center")
                    
            except Exception as img_error:
                print(f"Erro ao carregar imagem do sensor: {img_error}")
                canvas.create_text(center_x, center_y, 
                                 text=f"Erro ao carregar imagem\nÂngulo: {sensor_angle}° | Posição: {position}", 
                                 font=("Arial", 12), fill="red", justify="center")
                
        except Exception as e:
            print(f"Erro geral no preview do sensor: {e}")
            canvas.create_text(200, 90, text="Erro ao carregar preview", 
                             font=("Arial", 12), fill="red")

    def remove_rail_from_fma(self):
        """Remove trilho selecionado da FMA"""
        selection = self.rails_listbox.curselection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um trilho para remover.")
            return
        
        index = selection[0]
        self.rails_listbox.delete(index)
        
        # Remover do elemento também
        if 'associated_rails' in self.current_fma_element and index < len(self.current_fma_element['associated_rails']):
            del self.current_fma_element['associated_rails'][index]
    
    def highlight_selected_sensor(self):
        """Destaca sensor selecionado no canvas"""
        selection = self.sensors_listbox.curselection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um sensor na lista.")
            return
        
        index = selection[0]
        if 'associated_sensors' not in self.current_fma_element or index >= len(self.current_fma_element['associated_sensors']):
            return
        
        sensor_ref_id = self.current_fma_element['associated_sensors'][index]['refId']
        
        # Encontrar e destacar sensor
        for element in self.trackplan_elements:
            if element.get('type') == 'sensor' and str(element.get('id', '')) == sensor_ref_id:
                self.highlight_element(element, temporary=True, duration_ms=3000, color="yellow")
                break
    
    def highlight_selected_rail(self):
        """Destaca trilho selecionado no canvas"""
        selection = self.rails_listbox.curselection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um trilho na lista.")
            return
        
        index = selection[0]
        if 'associated_rails' not in self.current_fma_element or index >= len(self.current_fma_element['associated_rails']):
            return
        
        rail_ref_id = self.current_fma_element['associated_rails'][index]['refId']
        
        # Encontrar e destacar trilho
        for element in self.trackplan_elements:
            if element.get('type') in ['rail', 'switch', 'link', 'crossing'] and str(element.get('id', '')) == rail_ref_id:
                self.highlight_element(element, temporary=True, duration_ms=3000, color="orange")
                break
    
    def test_fma_highlights(self):
        """Testa visualmente a FMA destacando todos os seus trilhos e sensores em azul claro"""
        if not self.current_fma_element:
            return

        # Limpar destaques anteriores
        self.clear_all_highlights()

        highlighted_count = 0
        failed_count = 0

        # Destacar trilhos associados usando função unificada
        for rail_data in self.current_fma_element.get('associated_rails', []):
            rail_ref_id = rail_data.get('refId', '')
            for element in self.trackplan_elements:
                if element.get('type') == "auto_rail":
                    continue
                if element.get('type') in ['rail', 'switch', 'link', 'crossing'] and str(element.get('id', '')) == rail_ref_id:
                    success = self.highlight_element(element, temporary=False, color="lightblue")
                    if success:
                        highlighted_count += 1
                    else:
                        failed_count += 1
                    break
            else:
                failed_count += 1

        # Destacar sensores associados usando função unificada com contexto FMA
        for sensor_data in self.current_fma_element.get('associated_sensors', []):
            sensor_ref_id = sensor_data.get('refId', '')
            fma_position = sensor_data.get('fmaPosition', 'right')  # Extrair posição da FMA
            for element in self.trackplan_elements:
                if element.get('type') == 'sensor' and str(element.get('id', '')) == sensor_ref_id:
                    # Usar função unificada com contexto da FMA para destacamento correto
                    success = self.highlight_element(element, temporary=False, fma_position=fma_position, color="lightblue")
                    if success:
                        highlighted_count += 1
                    else:
                        failed_count += 1
                    break
            else:
                failed_count += 1

        # Destacar a própria FMA usando função unificada
        if self.current_fma_element:
            success = self.highlight_element(self.current_fma_element, temporary=False, color="darkblue")
            if success:
                highlighted_count += 1
            else:
                failed_count += 1
                # Fallback para destacar o texto em azul escuro
                if 'text_id' in self.current_fma_element:
                    self.trackplan_canvas.itemconfig(self.current_fma_element['text_id'], fill="darkblue")
                    if not hasattr(self, 'highlighted_fma_elements'):
                        self.highlighted_fma_elements = []
                    if self.current_fma_element not in self.highlighted_fma_elements:
                        self.highlighted_fma_elements.append(self.current_fma_element)
                    highlighted_count += 1

        messagebox.showinfo("Teste FMA", f"FMA '{self.current_fma_element['name']}' testada!\n{highlighted_count} elementos destacados, {failed_count} falhas.")
    
    def highlight_element(self, element, temporary=False, duration_ms=3000, fma_position=None, color=None):
        """
        Função unificada para destacar elementos
        
        Args:
            element: Elemento a ser destacado (rail, switch, sensor, fma)
            temporary: Se True, destaque temporário; se False, permanente
            duration_ms: Duração do destaque temporário em milissegundos
            fma_position: Posição específica para sensores ('left' ou 'right')
            color: Cor do destaque (para compatibilidade, mas usa imagens azuis quando disponível)
            
        Returns:
            bool: True se o destaque foi aplicado com sucesso, False caso contrário
        """
        success = False
        element_type = element.get('type')
        
        try:
            if element_type in ['rail', 'switch', 'link', 'crossing']:
                success = self.highlight_rail_switch_or_link_blue(element, temporary=temporary, duration_ms=duration_ms)
                
            elif element_type == 'sensor':
                if fma_position and fma_position in ['left', 'right']:
                    success = self.highlight_sensor_blue_with_context(element, temporary=temporary, duration_ms=duration_ms, fma_position=fma_position)
                else:
                    success = self.highlight_sensor_blue_with_context(element, temporary=temporary, duration_ms=duration_ms, fma_position=None)
                    
            elif element_type == 'fma':
                success = self.highlight_fma_blue(element, temporary=temporary, duration_ms=duration_ms)
            
            # Adicionar à lista de destacados apenas se permanente e bem-sucedido
            if success and not temporary:
                if not hasattr(self, 'highlighted_fma_elements'):
                    self.highlighted_fma_elements = []
                if element not in self.highlighted_fma_elements:
                    self.highlighted_fma_elements.append(element)
            
            if not success:
                print(f"Não foi possível destacar {element_type} com ID {element.get('id', 'N/A')}")
                
        except Exception as e:
            print(f"Erro ao destacar elemento: {e}")
            return False
        
        return success

    # === FUNÇÕES DE APOIO PARA HIGHLIGHT ===
    
    def highlight_rail_switch_or_link_blue(self, element, temporary=False, duration_ms=3000):
        """Destaca trilho, switch ou link com imagem azul"""
        try:
            # Verificar se elemento tem canvas_id válido (rails usam canvas_ids plural)
            has_canvas_id = False
            canvas_id_to_use = None

            if 'canvas_ids' in element and element['canvas_ids'] and len(element['canvas_ids']) > 0:
                # Para rails que usam canvas_ids plural - PRIORIDADE MAIS ALTA
                has_canvas_id = True
                canvas_id_to_use = element['canvas_ids'][0]
            elif 'canvas_id' in element and element['canvas_id']:
                # Para switches, links e outros elementos que usam canvas_id singular
                has_canvas_id = True
                canvas_id_to_use = element['canvas_id']  # Usar o primeiro ID

            if not has_canvas_id:
                return False

            # Determinar a chave da imagem baseada no tipo e propriedades
            angle = int(element.get('angle', 0))
            mirror = int(element.get('mirror', 0))
            rail_type = element.get('rail_type')
            element_type = element.get('type')

            # Detectar se é switch: rail_type='SWITCH' OU type='switch'
            is_switch = (rail_type == 'SWITCH' or element_type == 'switch')
            is_link = (rail_type == 'link' or element_type == 'link')
            is_crossing = (element_type == 'crossing' or rail_type == 'CROSSING')

            if is_switch:
                image_key = f"switch_{angle}_{mirror}"
            elif is_link:
                image_key = f"link_{angle}"
            elif is_crossing:
                image_key = f"crossing_{angle}"
            else:
                # Rails normais (rail_type pode ser 'line', None, ou ausente)
                image_key = f"rail_{angle}_{mirror}"

            # Verificar se existe imagem azul correspondente
            if hasattr(self, 'blue_element_images') and image_key in self.blue_element_images:
                # Salvar imagem original se não foi salva ainda
                if 'original_image_key' not in element or not element.get('original_image_key'):
                    normal_key = image_key
                    element['original_image_key'] = normal_key if hasattr(self, 'element_images') and normal_key in self.element_images else None

                # Aplicar imagem azul
                self.trackplan_canvas.itemconfig(canvas_id_to_use, image=self.blue_element_images[image_key])

                # Se temporário, restaurar após o tempo especificado
                if temporary and duration_ms > 0:
                    self.root.after(duration_ms, lambda e=element: self.restore_original_image(e))
                return True
            # Fallback para mudança de cor se não houver imagem azul
            return self.highlight_fallback_color(element, temporary, duration_ms)
        except Exception as e:
            print(f"Erro ao destacar rail/switch: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def ensure_sensor_position(self, sensor_element):
        """Garante que o sensor tenha uma posição válida (left/right) baseada na FMA associada"""
        sensor_id = str(sensor_element.get('id', ''))
        if not sensor_id:
            return sensor_element.get('position', 'right')
        # Procurar em todas as FMAs para encontrar este sensor
        for fma_element in self.trackplan_elements:
            if fma_element.get('type') == 'fma':
                for sensor_data in fma_element.get('associated_sensors', []):
                    if str(sensor_data.get('refId')) == sensor_id:
                        # Encontrou o sensor associado à FMA, retornar a posição definida
                        position = sensor_data.get('fmaPosition', 'right')
                        if position in ('left', 'right'):
                            return position
        
        # Se não encontrou em nenhuma FMA, usar default 'right' mas SEM modificar o sensor
        # Retornar apenas a posição, não armazenar no sensor
        return sensor_element.get('position', 'right')  # Usar posição existente ou 'right' como padrão
    
    def highlight_sensor_blue(self, element, temporary=False, duration_ms=3000):
        """Destaca sensor com imagem azul (atalho para a versão com contexto).
        Mantém a API existente delegando para highlight_sensor_blue_with_context."""
        return self.highlight_sensor_blue_with_context(
            element,
            temporary=temporary,
            duration_ms=duration_ms,
            fma_position=None,
        )
    
    def highlight_sensor_blue_with_context(self, element, temporary=False, duration_ms=3000, fma_position=None):
        """Destaca sensor com imagem azul usando contexto específico da FMA"""
        try:
            if 'canvas_id' not in element or not element['canvas_id']:
                return False
                
            position = fma_position if fma_position in ('left', 'right') else self.ensure_sensor_position(element)
            angle = int(element.get('angle', 0))
            image_key = f"sensor_{angle}_{position}"
            
            # Verificar se existe imagem azul correspondente
            if hasattr(self, 'blue_element_images') and image_key in self.blue_element_images:
                # Salvar imagem original se não foi salva ainda
                if 'original_image_key' not in element or not element.get('original_image_key'):
                    normal_key = f"sensor_{angle}"
                    element['original_image_key'] = normal_key if hasattr(self, 'element_images') and normal_key in self.element_images else None
                
                # Aplicar imagem azul
                self.trackplan_canvas.itemconfig(element['canvas_id'], image=self.blue_element_images[image_key])
                
                # Se temporário, restaurar após o tempo especificado
                if temporary and duration_ms > 0:
                    self.root.after(duration_ms, lambda: self.restore_original_image(element))
                
                # Destacar símbolo também se existir (fallback para cor)
                if 'symbol_id' in element and element['symbol_id']:
                    try:
                        self.trackplan_canvas.itemconfig(element['symbol_id'], fill="lightblue")
                        if temporary:
                            self.root.after(duration_ms, lambda: self.trackplan_canvas.itemconfig(element['symbol_id'], fill="red"))
                    except tk.TclError:
                        pass  # Ignorar se não conseguir destacar o símbolo
                
                return True
            else:
                # Fallback para mudança de cor se não houver imagem azul
                return self.highlight_fallback_color(element, temporary, duration_ms)
                
        except Exception as e:
            print(f"Erro ao destacar sensor com contexto: {e}")
            return False
    
    def highlight_fma_blue(self, element, temporary=False, duration_ms=3000):
        """Destaca FMA com imagem azul gerada dinamicamente e seus rails automáticos associados"""
        try:
            if 'canvas_id' not in element or not element.get('canvas_id'):
                return False

            # Verificar se não é um rail automático disfarçado
            if element.get("type") != "fma":
                return False

            # Obter dados da FMA
            fma_angle = int(element.get('angle', 0))
            fma_name = element.get('name', 'FMA')
            cache_key = f"fma_blue_{fma_angle}_{fma_name}"

            # Verificar se já existe no cache
            if not hasattr(self, 'fma_blue_cache'):
                self.fma_blue_cache = {}

            if cache_key not in self.fma_blue_cache:
                # Gerar imagem azul dinamicamente
                blue_image = self.create_fma_blue_image_with_integrated_text(fma_angle, fma_name)
                if not blue_image:
                    return False
                self.fma_blue_cache[cache_key] = blue_image

            # Salvar imagem original antes de aplicar a azul
            if 'original_image_key' not in element:
                element['original_image_key'] = f"fma_{fma_angle}_{fma_name}"

            # Aplicar imagem azul na FMA
            self.trackplan_canvas.itemconfig(element['canvas_id'], image=self.fma_blue_cache[cache_key])

            # Armazenar referência para evitar garbage collection
            if not hasattr(self, 'temp_image_refs'):
                self.temp_image_refs = []
            self.temp_image_refs.append(self.fma_blue_cache[cache_key])

            if temporary and duration_ms > 0:
                self.root.after(duration_ms, lambda e=element: self.restore_original_image(e))
            return True

        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def highlight_fallback_color(self, element, temporary=False, duration_ms=3000):
        """Fallback para destacamento por cor quando não há imagem azul"""
        try:
            element_type = element.get('type', 'unknown')
            element_id = element.get('id', 'unknown')

            # Verificar se o elemento tem canvas_id ou canvas_ids
            if 'canvas_id' not in element and 'canvas_ids' not in element:
                return False

            # Para rails com múltiplos canvas_ids, destacar todos
            if element.get('canvas_ids') and element['canvas_ids']:
                success = False
                for i, cid in enumerate(element['canvas_ids']):
                    if cid:
                        try:
                            # Salvar estado original
                            if '_orig_fill' not in element:
                                element['_orig_fill'] = []
                                element['_orig_outline'] = []

                            element['_orig_fill'].append(self.trackplan_canvas.itemcget(cid, 'fill'))
                            element['_orig_outline'].append(self.trackplan_canvas.itemcget(cid, 'outline'))

                            # Aplicar destaque azul
                            if element['_orig_fill'][-1] != '':
                                self.trackplan_canvas.itemconfig(cid, fill='#87CEFA')
                            else:
                                self.trackplan_canvas.itemconfig(cid, outline='#87CEFA')
                            success = True
                        except tk.TclError as e:
                            print(f"Erro no canvas_id[{i}]: {e}")
                            continue

                if success and temporary and duration_ms > 0:
                    self.root.after(duration_ms, lambda e=element: self.restore_original_image(e))
                return success

            # Para elementos com canvas_id único
            elif 'canvas_id' in element and element['canvas_id']:
                cid = element['canvas_id']
                print(f"   Canvas_id único: {cid}")
                try:
                    element['_orig_fill'] = self.trackplan_canvas.itemcget(cid, 'fill')
                    element['_orig_outline'] = self.trackplan_canvas.itemcget(cid, 'outline')

                    # Aplicar destaque
                    if element['_orig_fill'] != '':
                        self.trackplan_canvas.itemconfig(cid, fill='#87CEFA')
                    else:
                        self.trackplan_canvas.itemconfig(cid, outline='#87CEFA')
                except tk.TclError as e:
                    print(f"Erro no canvas_id único: {e}")
                    return False

                if temporary and duration_ms > 0:
                    self.root.after(duration_ms, lambda e=element: self.restore_original_image(e))
                return True

            print(f"Fallback: Nenhuma condição atendida para {element_type} ID {element_id}")
            return False
        except Exception as e:
            print(f"Erro no fallback de cor: {e}")
            return False
    
    def restore_original_image(self, element):
        """Restaura a imagem original do elemento"""
        try:
            etype = element.get('type')

            # Verificar se é um rail automático e ignorar
            if etype == "rail":
                is_auto_rail = (
                    element.get("auto_rail", False) or
                    element.get("rail_type") == "AUTO" or
                    (element.get("id", 0) >= 6000 and element.get("id", 0) < 7000 and 
                     element.get("parent_element") is not None)  # Só considerar auto se tiver parent_element
                )
                if is_auto_rail:
                    return

            # Restaurar fallback por cor
            if element.get('_orig_fill') is not None or element.get('_orig_outline') is not None:
                # Para rails com múltiplos canvas_ids
                if element.get('canvas_ids') and isinstance(element.get('_orig_fill'), list):
                    for i, cid in enumerate(element['canvas_ids']):
                        if cid and i < len(element['_orig_fill']):
                            try:
                                if element['_orig_fill'][i] not in (None, ''):
                                    self.trackplan_canvas.itemconfig(cid, fill=element['_orig_fill'][i])
                                if element['_orig_outline'][i] not in (None, ''):
                                    self.trackplan_canvas.itemconfig(cid, outline=element['_orig_outline'][i])
                            except Exception:
                                pass
                # Para elementos com canvas_id único
                elif element.get('canvas_id'):
                    cid = element.get('canvas_id')
                    try:
                        if element.get('_orig_fill') not in (None, ''):
                            self.trackplan_canvas.itemconfig(cid, fill=element['_orig_fill'])
                        if element.get('_orig_outline') not in (None, ''):
                            self.trackplan_canvas.itemconfig(cid, outline=element['_orig_outline'])
                    except Exception:
                        pass
                    finally:
                        element.pop('_orig_fill', None)
                        element.pop('_orig_outline', None)            # Restaurar símbolo do sensor (se alterado)
            if etype == 'sensor' and element.get('symbol_id') and element.get('_symbol_fill') is not None:
                try:
                    self.trackplan_canvas.itemconfig(element['symbol_id'], fill=element['_symbol_fill'])
                except Exception:
                    pass
                finally:
                    element.pop('_symbol_fill', None)

            if etype == 'fma':
                # Regenerar imagem normal da FMA
                angle = element.get('angle', 0)
                name = element.get('name', 'FMA')
                original = self.create_fma_image_with_integrated_text(angle, name)
                if original and element.get('canvas_id'):
                    self.trackplan_canvas.itemconfig(element['canvas_id'], image=original)
                    # manter ref
                    if not hasattr(self, 'element_images'):
                        self.element_images = {}
                    element['image_key'] = f"fma_{angle}_{name}"
                    self.element_images[element['image_key']] = original
            else:
                # Rails/Switch/Sensor: voltar para imagem normal se houver
                original_key = element.get('original_image_key')
                if original_key and hasattr(self, 'element_images') and original_key in self.element_images:
                    # Para rails com canvas_ids (prioridade)
                    if element.get('canvas_ids') and element['canvas_ids']:
                        for cid in element['canvas_ids']:
                            if cid:
                                try:
                                    self.trackplan_canvas.itemconfig(cid, image=self.element_images[original_key])
                                except Exception:
                                    pass
                    # Para elementos com canvas_id único
                    elif element.get('canvas_id'):
                        self.trackplan_canvas.itemconfig(element['canvas_id'], image=self.element_images[original_key])

        except Exception as e:
            print(f"Erro ao restaurar imagem original: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_all_highlights(self):
        """Limpa todos os destaques aplicados"""
        try:
            # Restaurar imagens/cores dos itens destacados permanentemente
            if hasattr(self, 'highlighted_fma_elements'):
                for element in list(self.highlighted_fma_elements):
                    # Ignorar rails automáticos 
                    if element.get("type") != "rail" or not (
                        element.get("auto_rail", False) or
                        element.get("rail_type") == "AUTO" or
                        (element.get("id", 0) >= 6000 and element.get("id", 0) < 7000 and 
                         element.get("parent_element") is not None)  # Só considerar auto se tiver parent_element
                    ):
                        self.restore_original_image(element)
                self.highlighted_fma_elements.clear()

            # Itens temporários já são restaurados por after(); ainda assim,
            # tentar restaurar qualquer fallback pendente presente em elementos
            for element in self.trackplan_elements:
                # Ignorar rails automáticos
                if element.get("type") == "rail":
                    is_auto_rail = (
                        element.get("auto_rail", False) or
                        (element.get("id", 0) >= 6000 and element.get("id", 0) < 7000) or
                        element.get("rail_type") == "AUTO"
                    )
                    if is_auto_rail:
                        continue

                if element.get('_orig_fill') is not None or element.get('_orig_outline') is not None or element.get('_symbol_fill') is not None:
                    self.restore_original_image(element)

        except Exception as e:
            print(f"Erro ao limpar destaques: {e}")
            import traceback
            traceback.print_exc()

    # === Fluxo de seleção múltipla de trilhos/afins para FMA ===
    def start_fma_multi_pick_mode(self):
        """Ativa o modo de seleção de múltiplos elementos (rail/switch/link/crossing) para a FMA atual."""
        try:
            if not self.current_fma_element:
                messagebox.showwarning("Aviso", "Abra a configuração de uma FMA para usar esta função.")
                return
            # Iniciar estado
            self.fma_config_window.withdraw() # Ocultar janela de configuração da FMA
            self._fma_rail_pick_mode = True
            self._fma_pick_ids = set()
            self._fma_pick_types = {}
            if hasattr(self, '_fma_pick_info_var'):
                self._fma_pick_info_var.set("Seleção ativa: 0 escolhido(s). Use Salvar/Cancelar na mini janela.")

            # Abrir mini toplevel com botões Salvar/Cancelar (não modal)
            try:
                # Fechar anterior se existir
                if hasattr(self, '_fma_pick_window') and self._fma_pick_window and self._fma_pick_window.winfo_exists():
                    self._fma_pick_window.destroy()
                self._fma_pick_window = tk.Toplevel(self.root)
                self._fma_pick_window.title("Selecionar Elementos")
                self._fma_pick_window.geometry("220x90+100+100")
                self._fma_pick_window.attributes('-topmost', True)
                self._fma_pick_window.resizable(False, False)
                # Conteúdo simples
                frm = ttk.Frame(self._fma_pick_window, padding=8)
                frm.pack(fill='both', expand=True)
                lbl = ttk.Label(frm, text="Confirme a seleção:")
                lbl.pack(anchor='w', pady=(0,6))
                btns = ttk.Frame(frm)
                btns.pack(fill='x')
                save_btn = ttk.Button(btns, text="Salvar", command=self._fma_pick_confirm)
                cancel_btn = ttk.Button(btns, text="Cancelar", command=self._fma_pick_cancel)
                save_btn.pack(side='left', expand=True, fill='x', padx=(0,4))
                cancel_btn.pack(side='left', expand=True, fill='x')
                # Fechamento da janela também cancela
                self._fma_pick_window.protocol("WM_DELETE_WINDOW", lambda: self._fma_pick_cancel())
            except Exception as e:
                print(f"Erro ao criar mini janela de seleção: {e}")
        except Exception as e:
            print(f"Erro ao iniciar modo de seleção: {e}")

    def _fma_pick_handle_click(self, grid_x, grid_y):
        """Processa cliques no canvas durante o modo de seleção (toggle de elemento permitido)."""
        try:
            # Encontrar elemento clicado
            element = self.get_element_at_position(grid_x, grid_y)
            if not element:
                return
            et = element.get('type')
            if et not in {'rail', 'switch', 'link', 'crossing'}:
                return
            
            if et == 'rail' and element.get('auto_rail'):
                return

            eid = str(element.get('id'))
            # Toggle
            if eid in self._fma_pick_ids:
                self._fma_pick_ids.remove(eid)
                self._fma_pick_types.pop(eid, None)
                self._unhighlight_element_for_pick(element)
            else:
                self._fma_pick_ids.add(eid)
                self._fma_pick_types[eid] = et
                self._highlight_element_for_pick(element)

            if hasattr(self, '_fma_pick_info_var'):
                self._fma_pick_info_var.set(f"Seleção ativa: {len(self._fma_pick_ids)} escolhido(s). Enter confirma, Esc cancela.")
        except Exception as e:
            print(f"Erro no pick click: {e}")

    def _fma_pick_confirm(self, event=None):
        """Confirma a seleção atual e associa os elementos à FMA (um undo por item)."""
        try:
            self.fma_config_window.deiconify()
            if not getattr(self, '_fma_rail_pick_mode', False):
                return
            if not self.current_fma_element:
                return
            if not hasattr(self.current_fma_element, 'setdefault'):
                return

            assoc = self.current_fma_element.setdefault('associated_rails', [])

            existing = set()
            for r in assoc:
                rid = str(r.get('refId'))
                if rid:
                    existing.add(rid)

            for eid in list(self._fma_pick_ids):
                if eid in existing:
                    continue

                self.save_state_for_undo()

                picked_type = self._fma_pick_types.get(eid, 'rail')
                item = {
                    'refId': eid,
                    'auto': False,
                    'type': picked_type
                }

                if picked_type == 'crossing':
                    for elm in self.trackplan_elements:
                        if str(elm.get('id')) == eid:
                            cross_angle = int(elm.get('angle', 0))
                    
                    source = None
                    
                    self.crossing_way_window = tk.Toplevel(self.root)
                    self.crossing_way_window.title("Selecionar Caminhos do Cruzamento")
                    self.crossing_way_window.geometry("220x90+100+100")
                    self.crossing_way_window.attributes('-topmost', True)
                    self.crossing_way_window.resizable(False, False)
                    # Conteúdo simples
                   
                    frm = ttk.Frame(self.crossing_way_window, padding=8)
                    frm.pack(fill='both', expand=True)
                    lbl = ttk.Label(frm, text="Cruzamento selecionado!\nDefina os caminhos:")
                    lbl.pack(anchor='w', pady=(0,6))
                    btns = ttk.Frame(frm)


                    if source is not None:
                        item['from'] = source.get('from', 0)
                        item['to'] = source.get('to', 0)
                    else:
                        item['from'] = 0
                        item['to'] = 0

                assoc.append(item)

                # Feedback visual: destacar em azul por 3s
                try:
                    # Encontrar elemento por id
                    target = None
                    for el in self.trackplan_elements:
                        if str(el.get('id')) == eid:
                            target = el
                            break
                    if target:
                        self.highlight_rail_switch_or_link_blue(target, temporary=True, duration_ms=3000)
                except Exception:
                    pass

            # Sair do modo
            self._fma_pick_cleanup_highlights()
            self._fma_rail_pick_mode = False
            self._fma_pick_ids.clear()
            # Atualizar UI de associações (lista de trilhos etc.)
            try:
                self.refresh_fma_associations_ui()
            except Exception:
                pass
            # Fechar mini janela se aberta
            try:
                if hasattr(self, '_fma_pick_window') and self._fma_pick_window and self._fma_pick_window.winfo_exists():
                    self._fma_pick_window.destroy()
            except Exception:
                pass
            if hasattr(self, '_fma_pick_info_var'):
                self._fma_pick_info_var.set("Seleção concluída.")
        except Exception as e:
            print(f"Erro ao confirmar seleção: {e}")

    def _fma_pick_cancel(self, event=None, silent=False):
        """Cancela o modo de seleção e remove destaques verdes."""
        try:
            if not getattr(self, '_fma_rail_pick_mode', False):
                return
            self._fma_pick_cleanup_highlights()
            self._fma_rail_pick_mode = False
            if hasattr(self, '_fma_pick_ids'):
                self._fma_pick_ids.clear()
            # Fechar mini janela se aberta
            try:
                if hasattr(self, '_fma_pick_window') and self._fma_pick_window and self._fma_pick_window.winfo_exists():
                    self._fma_pick_window.destroy()
            except Exception:
                pass
            if hasattr(self, '_fma_pick_info_var') and not silent:
                self._fma_pick_info_var.set("Seleção cancelada.")
        except Exception as e:
            print(f"Erro ao cancelar seleção: {e}")

    def refresh_fma_associations_ui(self):
        """Atualiza a UI de associações da FMA (lista/árvore de trilhos e afins)."""
        try:
            assoc = (self.current_fma_element or {}).get('associated_rails', [])

            if hasattr(self, '_associated_rails_tree') and self._associated_rails_tree:
                tree = self._associated_rails_tree
                for iid in tree.get_children():
                    tree.delete(iid)
                for item in assoc:
                    rid = item.get('refId')
                    rtype = item.get('type', '')
                    extra = ""
                    if rtype == "crossing":
                        extra = f" from={item.get('from', '')} to={item.get('to', '')}"
                    tree.insert('', 'end', values=(rid, rtype + extra))

            if hasattr(self, '_associated_rails_var') and isinstance(self._associated_rails_var, tk.Variable):
                items = []
                for a in assoc:
                    text = f"{a.get('refId')} ({a.get('type', '')})"
                    if a.get('type') == 'crossing':
                        text += f" [from={a.get('from', '')}, to={a.get('to', '')}]"
                    items.append(text)
                try:
                    self._associated_rails_var.set(items)
                except Exception:
                    pass

            if hasattr(self, 'rails_listbox') and self.rails_listbox:
                try:
                    self.rails_listbox.delete(0, tk.END)
                    for item in assoc:
                        rid = item.get('refId', 'N/A')
                        if item.get('type') == 'crossing':
                            rid = f"{rid} (from={item.get('from', '')}, to={item.get('to', '')})"
                        self.rails_listbox.insert(tk.END, rid)
                except Exception:
                    pass
        except Exception as e:
            print(f"Erro ao atualizar UI de associações: {e}")

    def _fma_pick_cleanup_highlights(self):
        try:
            # Remover retângulos verdes de todos os elementos com pick_highlight_id
            for el in list(getattr(self, 'trackplan_elements', [])):
                if isinstance(el, dict) and 'pick_highlight_id' in el:
                    try:
                        self.trackplan_canvas.delete(el['pick_highlight_id'])
                    except Exception:
                        pass
                    el.pop('pick_highlight_id', None)
            # Remover tags residuais
            try:
                self.trackplan_canvas.delete('fma_pick')
            except Exception:
                pass
        except Exception as e:
            print(f"Erro ao limpar destaques (pick): {e}")
    
    def save_fma_config(self):
        """Salva as configurações da FMA com validação de tipo"""
        if not self.current_fma_element:
            messagebox.showerror("Erro", "Nenhuma FMA selecionada.")
            return
        
        # Validar ID
        fma_id = self.fma_id_var.get().strip()
        if not fma_id:
            messagebox.showerror("Erro", "ID da FMA é obrigatório!")
            return
        
        # Verificar se ID tem prefixo correto baseado no tipo selecionado
        is_fma1 = self.fma_type_var.get()
        expected_prefix = "3" if is_fma1 else "4"
        
        if not fma_id.startswith(expected_prefix):
            response = messagebox.askyesno("Correção Automática", 
                f"O ID '{fma_id}' não tem o prefixo correto para {'FMA1' if is_fma1 else 'FMA2'}.\n\n"
                f"Deseja corrigir automaticamente para '{expected_prefix}{fma_id.lstrip('34')}'?")
            if response:
                base_number = fma_id.lstrip('34')  # Remove prefixos 3 ou 4 existentes
                corrected_id = f"{expected_prefix}{base_number}"
                self.fma_id_var.set(corrected_id)
                fma_id = corrected_id
            else:
                return
        
        # Verificar se ID é numérico após o prefixo
        base_id = fma_id[1:]  # Remove o prefixo
        if not base_id.isdigit():
            response = messagebox.askyesno("Aviso", 
                                        f"O ID '{fma_id}' não é completamente numérico.\n\n"
                                        "Recomenda-se usar apenas números após o prefixo.\n"
                                        "Continuar mesmo assim?")
            if not response:
                return
        
        # Verificar se ID já existe em outros elementos
        for element in self.trackplan_elements:
            if (element != self.current_fma_element and 
                str(element.get('id', '')) == fma_id):
                messagebox.showerror("Erro", 
                                f"O ID '{fma_id}' já está sendo usado por outro elemento!\n"
                                "Escolha um ID único.")
                return
        
        # Atualizar dados da FMA
        self.current_fma_element['id'] = fma_id
        self.current_fma_element['name'] = self.fma_name_var.get().upper()
        self.current_fma_element['angle'] = int(self.fma_angle_var.get())
        self.current_fma_element['ref_id'] = self.fma_ref_id_var.get()
        self.current_fma_element['fma_type'] = 'FMA1' if is_fma1 else 'FMA2'
        
        # Atualizar nome no canvas
        if 'text_id' in self.current_fma_element:
            self.trackplan_canvas.itemconfig(self.current_fma_element['text_id'], text=self.current_fma_element['name'])
        
        messagebox.showinfo("Sucesso", f"Configuração da FMA {self.current_fma_element['fma_type']} '{self.current_fma_element['name']}' salva com sucesso!")
        self.close_fma_config()
        self._mark_content_changed()
        self.refresh_fma_test_window()
    
    def close_fma_config(self):
        """Fecha janela de configuração da FMA"""
        self.clear_all_highlights()
        # Cancelar modo de seleção se ativo e limpar destaques verdes
        try:
            if getattr(self, '_fma_rail_pick_mode', False):
                self._fma_pick_cancel(silent=True)
        except Exception:
            pass
        if self.fma_config_window:
            try:
                self.fma_config_window.destroy()
            except Exception:
                pass
        self.fma_config_window = None
        self.current_fma_element = None
        self.restore_canvas_bindings()
        self.refresh_fma_test_window()

    def edit_link(self):
        """Abre o editor de url do link"""
        link_element = [elem for elem in self.selected_elements if isinstance(elem, dict) and elem.get('type') == 'link']  
        
        if not link_element:
            messagebox.showwarning("Aviso", "Selecione um link para continuar.")
            return

        if len(link_element) > 1:
            messagebox.showwarning("Aviso", "Selecione apenas um link para configurar.")
            return
        self.current_link_element = link_element[0]

        self.link_editor_window = tk.Toplevel(self.root)
        self.link_editor_window.title(f"Editando link")
        self.link_editor_window.transient(self.root)

        # Centralizar janela
        self.link_editor_window.update_idletasks()
        x = (self.link_editor_window.winfo_screenwidth() // 2) - 225
        y = (self.link_editor_window.winfo_screenheight() // 2) - 90
        self.link_editor_window.geometry(f"450x280+{x}+{y}")
    
        #Frame principal
        main_frame = ttk.Frame(self.link_editor_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Label principal
        title_label = ttk.Label(main_frame, text="Editar URL do Link", 
                            font=("Arial", 12, "bold"))
        title_label.pack(pady=(0, 15))
        
        # Frame para URL
        url_frame = ttk.LabelFrame(main_frame, text="URL de Destino", padding="10")
        url_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Campo de entrada para URL
        ttk.Label(url_frame, text="IP Address Net1 do Trackplan de destino:", 
                font=("Arial", 9)).pack(anchor="w", pady=(0, 5))
        
        self.link_url_var = tk.StringVar(value=self.current_link_element.get('url', ''))
        url_entry = ttk.Entry(url_frame, textvariable=self.link_url_var, 
                            font=("Arial", 10), width=40)
        url_entry.pack(fill=tk.X, pady=(0, 5))
        url_entry.focus()
        url_entry.select_range(0, tk.END)
        
        # Info sobre formato
        info_label = ttk.Label(url_frame, 
                            text="💡 Exemplo: 192.168.1.28 ou http://192.168.1.28",
                            font=("Arial", 8), foreground="gray")
        info_label.pack(anchor="w")

        checkbox_link = ttk.Checkbutton(url_frame, text="")

        #Frame Botões
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        #Botões
        ttk.Button(button_frame, text="Salvar", command=self.save_link_url).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Cancelar", command=self.close_link_editor).pack(side=tk.LEFT, padx=(10, 0))

        #Bind Enter para Salvar
        self.link_editor_window.bind('<Return>', lambda e: self.save_link_url())
        self.link_editor_window.bind('<Escape>', lambda e: self.close_link_editor())

    def save_link_url(self):
        """ Salva a URL editada dum link"""
        try:
            if not self.current_link_element:
                messagebox.showerror("Erro", "Nenhum link selecionado.")
                return
            
            # Obter URL do campo
            new_url = self.link_url_var.get().strip()
            
            if not new_url:
                messagebox.showwarning("Aviso", "A URL não pode estar vazia.")
                return
            
            # Normalizar URL (adicionar http:// se necessário)
            if new_url and not (new_url.startswith("http://") or new_url.startswith("https://")):
                new_url = f"http://{new_url}"
            
            # Salvar estado para undo
            self.save_state_for_undo()
            
            # Atualizar URL do link
            self.current_link_element['url'] = new_url
            self._mark_content_changed()
            
            messagebox.showinfo("Sucesso", f"URL do link atualizada para:\n{new_url}")
            self.close_link_editor()
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar URL: {e}")

    def close_link_editor(self):
        """Fecha a janela de edição do link"""
        if hasattr(self, 'link_editor_window') and self.link_editor_window:
            self.link_editor_window.destroy()
        self.link_editor_window = None
        self.current_link_element = None

    def open_sensor_editor(self):
        """Abre o editor de Sensor para elementos selecionados"""
        # Filtrar apenas sensores (ignorar células vazias que são tuplas)
        sensor_elements = [elem for elem in self.selected_elements 
                          if isinstance(elem, dict) and elem.get('type') in ['axle_counter', 'sensor']]
        
        if not sensor_elements:
            messagebox.showwarning("Aviso", "Selecione um sensor para editar.")
            return
        
        if len(sensor_elements) > 1:
            messagebox.showwarning("Aviso", "Selecione apenas um sensor por vez para edição.")
            return
        
        # Fechar janela anterior se existir
        if hasattr(self, 'sensor_config_window') and self.sensor_config_window and self.sensor_config_window.winfo_exists():
            self.sensor_config_window.destroy()
        
        # Armazenar referência do sensor atual
        self.current_sensor_element = sensor_elements[0]
        
        # Criar nova janela de configuração
        self.create_sensor_config_window()
    
    def create_sensor_config_window(self):
        """Cria janela de configuração para Sensor"""
        self.sensor_config_window = tk.Toplevel(self.root)
        self.sensor_config_window.title(f"Configuração Sensor - {self.current_sensor_element.get('name', 'Sem nome')}")
        self.sensor_config_window.geometry("500x400")
        self.sensor_config_window.transient(self.root)
        
        # Frame principal
        main_frame = ttk.Frame(self.sensor_config_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # === TÍTULO ===
        title_label = ttk.Label(main_frame, text="Configuração do Sensor", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # === DADOS BÁSICOS ===
        basic_frame = ttk.LabelFrame(main_frame, text="Informações do Sensor", padding="15")
        basic_frame.pack(fill=tk.X, pady=(0, 15))
        
        # ID do Sensor (Editável)
        row = 0
        ttk.Label(basic_frame, text="ID do Sensor:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=8)
        self.sensor_id_var = tk.StringVar(value=str(self.current_sensor_element.get('id', '')))
        id_entry = ttk.Entry(basic_frame, textvariable=self.sensor_id_var, width=20, font=("Arial", 10))
        id_entry.grid(row=row, column=1, sticky="w", padx=15, pady=8)

        # Referência para o id_entry
        self.slot_id_entry = id_entry

        # Bind para atualizar campos automáticos quando ID mudar
        self.sensor_id_var.trace_add('write', self.update_sensor_auto_fields)
        
        # Nome do Sensor (Gerado automaticamente - somente leitura)
        row += 1
        ttk.Label(basic_frame, text="Nome:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=8)
        self.sensor_name_var = tk.StringVar(value=self.current_sensor_element.get('name', ''))
        name_entry = ttk.Entry(basic_frame, textvariable=self.sensor_name_var, width=20, 
                              font=("Arial", 10), state="readonly", foreground="gray")
        name_entry.grid(row=row, column=1, sticky="w", padx=15, pady=8)

        # RefId (Gerado automaticamente - somente leitura)
        row += 1
        ttk.Label(basic_frame, text="Ref ID:", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=8)
        self.sensor_ref_id_var = tk.StringVar(value=self.current_sensor_element.get('ref_id', ''))
        ref_id_entry = ttk.Entry(basic_frame, textvariable=self.sensor_ref_id_var, width=20, 
                               font=("Arial", 10), state="readonly", foreground="gray")
        ref_id_entry.grid(row=row, column=1, sticky="w", padx=15, pady=8)
        
        # Posição (somente leitura)
        row += 1
        ttk.Label(basic_frame, text="Posição (x, y):", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=8)
        pos_text = f"({self.current_sensor_element.get('x', '?')}, {self.current_sensor_element.get('y', '?')})"
        ttk.Label(basic_frame, text=pos_text, font=("Arial", 10), foreground="gray").grid(row=row, column=1, sticky="w", padx=15, pady=8)
        
        # Possui FMA?
        row += 1
        initial_has_fma = bool(self.current_sensor_element.get('fma0')) or bool(self.current_sensor_element.get('fma1'))
        self.sensor_has_fma_var = tk.BooleanVar(value=initial_has_fma)
        ttk.Checkbutton(
            basic_frame,
            text="Possui FMA?",
            variable=self.sensor_has_fma_var,
            command=self.on_sensor_has_fma_toggle
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=8)
    
        # === BOTÕES ===
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(15, 0))
        
        # Botão Cancelar
        ttk.Button(buttons_frame, text="Cancelar", 
                  command=self.close_sensor_config).pack(side=tk.RIGHT, padx=(10, 0))
        
        # Botão Salvar
        ttk.Button(buttons_frame, text="Salvar", 
                  command=self.save_sensor_config).pack(side=tk.RIGHT)
        
        # Inicializar campos automáticos
        self.update_sensor_auto_fields()

        # Disparar salvar ao pressionar Enter (inclui Enter do teclado numérico)
        self.slot_id_entry.bind('<Return>', lambda e: self.save_sensor_config())
        self.slot_id_entry.bind('<KP_Enter>', lambda e: self.save_sensor_config())

        
        # Focar no campo ID
        id_entry.focus()
        id_entry.select_range(0, tk.END)
    
    def update_fma_auto_fields(self, *args, fma_check=None):
        """Atualiza automaticamente Nome e RefId baseado no ID da FMA e tipo (FMA1/FMA2)"""
        fma_id = self.fma_id_var.get().strip()
        fma_name = self.fma_name_var.get().strip().upper()

        print(f"DEBUG: update_fma_auto_fields chamado com fma_id='{fma_id}', fma_name='{fma_name}'")

        # Determinar se é FMA1 ou FMA2 baseado no checkbox
        is_fma1 = True  # Valor padrão
        if fma_check and hasattr(fma_check, 'instate'):
            is_fma1 = fma_check.instate(['selected'])
        elif hasattr(self, 'fma_type_var'):
            is_fma1 = self.fma_type_var.get()

        if fma_id:
            # Remover prefixo existente se houver (3 ou 4)
            if fma_id.startswith('3') or fma_id.startswith('4'):
                base_number = fma_id[1:]  # Remove o primeiro dígito
            else:
                base_number = fma_id
            
            # Aplicar prefixo correto baseado no tipo
            if is_fma1:
                # FMA1 - prefixo 3
                new_fma_id = f"3{base_number}"
            else:
                # FMA2 - prefixo 4  
                new_fma_id = f"4{base_number}"
            
            # Atualizar campos automaticamentec
            self.fma_id_var.set(new_fma_id)
            
            # RefId é sempre o mesmo (sem prefixo)
            ref_id = f"2{base_number}"
            self.fma_ref_id_var.set(ref_id)
            
            # Atualizar o elemento atual também
            if hasattr(self, 'current_fma_element') and self.current_fma_element:
                self.current_fma_element['id'] = int(new_fma_id) if new_fma_id.isdigit() else new_fma_id
                self.current_fma_element['name'] = fma_name
                self.current_fma_element['ref_id'] = ref_id
                self.current_fma_element['fma_type'] = 'FMA1' if is_fma1 else 'FMA2'
                
                # Atualizar visualização em tempo real
                self.update_fma_name_on_canvas(fma_name)                
        else:
            # Limpar campos se ID estiver vazio
            self.fma_name_var.set('')
            self.fma_ref_id_var.set('')

    def update_sensor_auto_fields(self, *args):
        """Atualiza automaticamente Nome e RefId baseado no ID"""
        sensor_id_input = self.sensor_id_var.get().strip()

        if sensor_id_input:
            # Manter apenas dígitos do input
            digits_only = ''.join(ch for ch in sensor_id_input if ch.isdigit())
            if not digits_only:
                # Nada válido para processar
                self.sensor_name_var.set('')
                self.sensor_ref_id_var.set('')
                return

            # Se já começa com '2', extrair a base após o primeiro dígito; caso contrário, usar tudo como base
            if digits_only.startswith('2'):
                base_number = digits_only[1:]
            else:
                base_number = digits_only

            # Se a base estiver vazia (usuário digitou apenas '2'), não preencher ainda
            if not base_number:
                self.sensor_id_var.set('2')
                self.sensor_name_var.set('')
                self.sensor_ref_id_var.set('')
                return

            # Construir ID do sensor: apenas prefixar '2' sem zero padding adicional
            new_sensor_id = f"2{base_number}"
            self.sensor_id_var.set(new_sensor_id)

            old_sensor_id = str(self.current_sensor_element.get('id', ''))

            # Nome automático e RefId derivados da base
            auto_name = f"ZP{base_number}"
            self.sensor_name_var.set(auto_name)
            ref_id = f"1{base_number}"
            self.sensor_ref_id_var.set(ref_id)

            # Atualizar o elemento atual também
            if hasattr(self, 'current_sensor_element') and self.current_sensor_element:
                self.current_sensor_element['id'] = new_sensor_id
                self.current_sensor_element['name'] = auto_name
                self.current_sensor_element['ref_id'] = ref_id

                self._update_sensor_references_in_fmas(old_sensor_id, new_sensor_id)
        else:
            # Limpar campos se ID estiver vazio
            self.sensor_name_var.set('')
            self.sensor_ref_id_var.set('')
    
    def _update_sensor_references_in_fmas(self, old_sensor_id, new_sensor_id):
        """Atualiza referências do sensor antigo para o novo em todas as FMAs"""
        if not old_sensor_id or not new_sensor_id or old_sensor_id == new_sensor_id:
            return
        
        updated_count = 0
        for fma in getattr(self, 'trackplan_elements', []):
            if fma.get('type') == 'fma':
                for sensor_data in fma.get('associated_sensors', []):
                    if sensor_data.get('refId') == old_sensor_id:
                        sensor_data['refId'] = new_sensor_id
                        updated_count += 1
            
    def test_sensor_highlight(self):
        """Destaca o sensor atual no canvas"""
        if not self.current_sensor_element:
            return
        
        # Limpar destaques anteriores
        self.clear_all_highlights()
        
        # Destacar sensor atual
        self.highlight_element(self.current_sensor_element, temporary=True, duration_ms=3000, color="yellow")
        
        messagebox.showinfo("Destaque", "Sensor destacado em azul no canvas!")
    
    def save_sensor_config(self):
        """Salva as configurações do sensor"""
        if not self.current_sensor_element:
            messagebox.showerror("Erro", "Nenhum sensor selecionado.")
            return
        
        # Validar ID
        sensor_id = self.sensor_id_var.get().strip()
        if not sensor_id:
            messagebox.showerror("Erro", "ID do sensor é obrigatório!")
            return
        
        # Verificar se ID é numérico (opcional, mas recomendado)
        if not sensor_id.isdigit():
            response = messagebox.askyesno("Aviso", 
                                         f"O ID '{sensor_id}' não é numérico.\n\n"
                                         "Recomenda-se usar apenas números para IDs de sensores.\n"
                                         "Continuar mesmo assim?")
            if not response:
                return
        
        # Verificar se ID já existe em outros elementos
        for element in self.trackplan_elements:
            if (element != self.current_sensor_element and 
                str(element.get('id', '')) == sensor_id):
                messagebox.showerror("Erro", 
                                   f"O ID '{sensor_id}' já está sendo usado por outro elemento!\n"
                                   "Escolha um ID único.")
                return
        
        # Salvar dados
        old_id = self.current_sensor_element.get('id', '')
        self.current_sensor_element['id'] = sensor_id
        self.current_sensor_element['name'] = self.sensor_name_var.get()
        self.current_sensor_element['ref_id'] = self.sensor_ref_id_var.get()
        
        # Manter/renomear FMAs conforme a flag
        try:
            has_fma = bool(getattr(self, 'sensor_has_fma_var', tk.BooleanVar(value=False)).get())
            self.ensure_sensor_fmas(self.current_sensor_element, has_fma, old_id=old_id)
        except Exception as e:
            print(f"Erro ao ajustar FMAs do sensor: {e}")

        # Atualizar texto no canvas se existir
        if 'text_id' in self.current_sensor_element:
            self.trackplan_canvas.itemconfig(self.current_sensor_element['text_id'], 
                                           text=self.current_sensor_element['name'])

        self.close_sensor_config()
        self._mark_content_changed()
        self.refresh_fma_test_window()
    
    def close_sensor_config(self):
        """Fecha janela de configuração do sensor"""
        self.clear_all_highlights()
        if hasattr(self, 'sensor_config_window') and self.sensor_config_window:
            self.sensor_config_window.destroy()
        self.sensor_config_window = None
        self.current_sensor_element = None

        self.refresh_fma_test_window()
    
    def delete_selected_elements(self):
        """Deleta todos os elementos selecionados"""
        try:
            if not hasattr(self, 'selected_elements') or not self.selected_elements:
                return
            
            elements_to_delete = []
            
            # Separar elementos reais de células vazias
            for item in self.selected_elements:
                if isinstance(item, dict):  # Elemento real
                    elements_to_delete.append(item)
                elif isinstance(item, tuple):  # Célula vazia (x, y)
                    grid_x, grid_y = item
                    # snapshot por célula vazia que resulte em remoção
                    self.save_state_for_undo()
                    self.remove_element_at_position(grid_x, grid_y)
            
            # Deletar elementos reais
            for element in elements_to_delete:
                # snapshot por item
                self.save_state_for_undo()
                self.delete_element(element)
            
            # Limpar seleção
            self.clear_selection()
            
            total_deleted = len(elements_to_delete)
            self.refresh_fma_test_window()
        except Exception as e:
            print(f"Erro ao deletar elementos selecionados: {e}")
    
    def select_all(self):
        """Seleciona todos os elementos no canvas"""
        self.clear_selection()
        
        # Selecionar todos os elementos
        count = 0
        for element in self.trackplan_elements:
            if element.get('type') == 'rail' and element.get('auto_rail'):
                continue
            self.select_element(element)
            count += 1
        
        if self.trackplan_elements:
            messagebox.showinfo("Sucesso", f"Todos os {count} elementos foram selecionados.")
        else:
            messagebox.showinfo("Aviso", "Não há elementos para selecionar.")
    
    def on_grid_right_click(self, event):
        """Gerencia clique direito na grade para menu de contexto de linhas/colunas"""
        # IMPORTANTE: Usar event.x/y diretamente, não canvasx/canvasy para detectar margens
        canvas_x = self.trackplan_canvas.canvasx(event.x)
        canvas_y = self.trackplan_canvas.canvasy(event.y)
        
        # Verificar se clicou na margem das linhas (margem esquerda)
        if canvas_x <= self.grid_size and canvas_y >= self.grid_size:
            # Calcular qual linha foi clicada
            row = int((canvas_y - self.grid_size) // self.grid_size)
            max_rows = int(self.height_var.get()) + 1
                        
            if 0 <= row < max_rows:
                self.show_row_context_menu(event, row)
                return "break"  # Impedir propagação do evento
            else:
                print(f"Linha {row} fora dos limites (0-{max_rows-1})")
        
        # Verificar se clicou na margem das colunas (margem superior)
        elif canvas_y <= self.grid_size and canvas_x >= self.grid_size:
            # Calcular qual coluna foi clicada
            column = int((canvas_x - self.grid_size) // self.grid_size)
            max_columns = int(self.width_var.get()) + 1            
            if 0 <= column < max_columns:
                self.show_column_context_menu(event, column)
                return "break"  # Impedir propagação do evento
            else:
                print(f"Coluna {column} fora dos limites (0-{max_columns-1})")
        
        # Se não foi clique nas margens, processar como clique normal no grid
        else:
            # Usar canvasx/canvasy para coordenadas do grid
            real_canvas_x = self.trackplan_canvas.canvasx(event.x)
            real_canvas_y = self.trackplan_canvas.canvasy(event.y)
            
            grid_x = int((real_canvas_x - self.grid_size) // self.grid_size)
            grid_y = int((real_canvas_y - self.grid_size) // self.grid_size)
            
            try:
                max_width = int(self.width_var.get())
                max_height = int(self.height_var.get())
            except:
                max_width = 71
                max_height = 21

        return "break"
    
    def show_row_context_menu(self, event, row):
        """Mostra menu de contexto para operações de linha"""
        
        # Inicializar atributos se não existirem
        if not hasattr(self, 'selected_rows'):
            self.selected_rows = set()
        if not hasattr(self, 'selected_columns'):
            self.selected_columns = set()
        if not hasattr(self, 'row_column_clipboard'):
            self.row_column_clipboard = {'type': None, 'data': None}
        
        self.selected_rows.clear()
        self.selected_columns.clear()
        self.selected_rows.add(row)
        
        # Destacar linha selecionada
        self.highlight_row(row)
        
        # Criar menu de contexto
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label=f"Selecionar Linha {row}", command=lambda: self.select_entire_row(row))
        context_menu.add_separator()
        context_menu.add_command(label="Inserir Linha Acima", command=lambda: self.insert_row_above(row))
        context_menu.add_command(label="Remover Linha", command=lambda: self.delete_row(row))
        context_menu.add_separator()
        context_menu.add_command(label="Copiar Linha", command=lambda: self.copy_row(row))
        context_menu.add_command(label="Recortar Linha", command=lambda: self.cut_row(row))
        
        if self.row_column_clipboard.get('type') == 'row':
            context_menu.add_command(label="Colar Linha", command=lambda: self.paste_row(row))
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            print(f"ERRO ao exibir menu: {e}")
            import traceback
            traceback.print_exc()
        finally:
            context_menu.grab_release()
    
    def show_column_context_menu(self, event, column):
        """Mostra menu de contexto para operações de coluna"""

        # Inicializar atributos se não existirem
        if not hasattr(self, 'selected_rows'):
            self.selected_rows = set()
        if not hasattr(self, 'selected_columns'):
            self.selected_columns = set()
        if not hasattr(self, 'row_column_clipboard'):
            self.row_column_clipboard = {'type': None, 'data': None}
        
        self.selected_rows.clear()
        self.selected_columns.clear()
        self.selected_columns.add(column)
        
        # Destacar coluna selecionada
        self.highlight_column(column)
        
        # Criar menu de contexto
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label=f"Selecionar Coluna {column}", command=lambda: self.select_entire_column(column))
        context_menu.add_separator()
        context_menu.add_command(label="Inserir Coluna à Esquerda", command=lambda: self.insert_column_left(column))
        context_menu.add_command(label="Remover Coluna", command=lambda: self.delete_column(column))
        context_menu.add_separator()
        context_menu.add_command(label="Copiar Coluna", command=lambda: self.copy_column(column))
        context_menu.add_command(label="Recortar Coluna", command=lambda: self.cut_column(column))
        
        if self.row_column_clipboard.get('type') == 'column':
            context_menu.add_command(label="Colar Coluna", command=lambda: self.paste_column(column))
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            print(f"ERRO ao exibir menu: {e}")
            import traceback
            traceback.print_exc()
        finally:
            context_menu.grab_release()
    
    def highlight_row(self, row):
        """Destaca uma linha inteira"""
        print(f"Destacando linha {row}")
        
        # Limpar destaques anteriores
        self.trackplan_canvas.delete("row_highlight")
        self.trackplan_canvas.delete("column_highlight")
        
        try:
            y = row * self.grid_size + self.grid_size
            width = int(self.width_var.get()) * self.grid_size
            
            # Criar retângulo de destaque
            highlight_id = self.trackplan_canvas.create_rectangle(
                self.grid_size, y, self.grid_size*2 + width, y + self.grid_size,
                outline="blue", width=3, fill="lightblue", stipple="gray25",
                tags="row_highlight"
            )
            print(f"Linha {row} destacada com ID {highlight_id}")
            
            # Agendar remoção do destaque após 3 segundos
            self.root.after(3000, lambda: self.trackplan_canvas.delete("row_highlight"))
            
        except Exception as e:
            print(f"Erro ao destacar linha {row}: {e}")
    
    def highlight_column(self, column):
        """Destaca uma coluna inteira"""

        # Limpar destaques anteriores
        self.trackplan_canvas.delete("row_highlight")
        self.trackplan_canvas.delete("column_highlight")
        
        try:
            x = column * self.grid_size + self.grid_size
            height = int(self.height_var.get()) * self.grid_size
            
            # Criar retângulo de destaque
            highlight_id = self.trackplan_canvas.create_rectangle(
                x, self.grid_size, x + self.grid_size, self.grid_size*2 + height,
                outline="green", width=3, fill="lightgreen", stipple="gray25",
                tags="column_highlight"
            )
                        
            # Agendar remoção do destaque após 3 segundos
            self.root.after(3000, lambda: self.trackplan_canvas.delete("column_highlight"))
            
        except Exception as e:
            print(f"Erro ao destacar coluna {column}: {e}")
    
    def select_entire_row(self, row):
        """Seleciona todos os elementos de uma linha"""
        try:
            self.clear_selection()
            
            # Selecionar elementos existentes na linha
            elements_selected = 0
            for element in self.trackplan_elements:
                if element.get('y') == row:
                    self.select_element(element)
                    elements_selected += 1
            
            # Selecionar células vazias na linha usando tuplas
            empty_cells_selected = 0
            try:
                max_width = int(self.width_var.get()) + 1
            except:
                max_width = 72
                
            for x in range(max_width):
                if not self.has_element_at_position(x, row):
                    # Usar tupla para célula vazia (consistente com select_empty_cell)
                    empty_cell = (x, row)
                    if empty_cell not in self.selected_elements:
                        self.selected_elements.append(empty_cell)
                        self.highlight_empty_cell(x, row)
                        empty_cells_selected += 1
            
            total_selected = elements_selected + empty_cells_selected

            # Atualizar info de seleção
            self.update_selection_info()
            
            # Mostrar resultado
            messagebox.showinfo("Seleção de Linha", 
                              f"Linha {row} selecionada:\n"
                              f"• {elements_selected} elementos\n"
                              f"• {empty_cells_selected} células vazias\n"
                              f"• {total_selected} total")
                              
        except Exception as e:
            print(f"Erro ao selecionar linha {row}: {e}")
            import traceback
            traceback.print_exc()
    
    def select_entire_column(self, column):
        """Seleciona todos os elementos de uma coluna"""
        try:
            self.clear_selection()
            
            # Selecionar elementos existentes na coluna
            elements_selected = 0
            for element in self.trackplan_elements:
                if element.get('x') == column:
                    self.select_element(element)
                    elements_selected += 1
            
            # Selecionar células vazias na coluna usando tuplas
            empty_cells_selected = 0
            try:
                max_height = int(self.height_var.get()) + 1
            except:
                max_height = 17
                
            for y in range(max_height):
                if not self.has_element_at_position(column, y):
                    # Usar tupla para célula vazia (consistente com select_empty_cell)
                    empty_cell = (column, y)
                    if empty_cell not in self.selected_elements:
                        self.selected_elements.append(empty_cell)
                        self.highlight_empty_cell(column, y)
                        empty_cells_selected += 1
            
            total_selected = elements_selected + empty_cells_selected
            
            # Atualizar info de seleção
            self.update_selection_info()
            
            # Mostrar resultado
            messagebox.showinfo("Seleção de Coluna", 
                              f"Coluna {column} selecionada:\n"
                              f"• {elements_selected} elementos\n"
                              f"• {empty_cells_selected} células vazias\n"
                              f"• {total_selected} total")
                              
        except Exception as e:
            print(f"Erro ao selecionar coluna {column}: {e}")
            import traceback
            traceback.print_exc()
        
        messagebox.showinfo("Seleção", f"Coluna {column} selecionada ({len(self.selected_elements)} posições)")
    
    def insert_row_above(self, row):
        """Insere uma nova linha acima da linha especificada"""
        try:
            switches_before = []
            for i, elem in enumerate(self.trackplan_elements):
                element_type = elem.get('type', 'unknown')
                rail_type = elem.get('rail_type', None)
                if element_type == 'switch' or (element_type == 'rail' and rail_type == 'SWITCH'):
                    switches_before.append((i, elem.get('id'), element_type, rail_type))

            # Salvar estado para undo usando a mesma função do undo/redo
            self.save_state_for_undo()

            # Primeiro, mover todos os elementos que estão na linha especificada ou abaixo
            moved_elements = 0
            elements_to_move = []

            # Coletar elementos que precisam ser movidos
            for element in self.trackplan_elements:
                current_y = element.get('y', -1)
                if current_y >= row:
                    elements_to_move.append(element)

            # Mover cada elemento
            for element in elements_to_move:
                old_y = element['y']
                element['y'] = old_y + 1
                moved_elements += 1

            # Aumentar altura do grid
            current_height = int(self.height_var.get())
            new_height = current_height + 1
            self.height_var.set(str(new_height))
            
            # Limpar por tags específicas
            canvas_tags = ["rail", "link", "sensor", "switch", "fma", "element", 
                        "selection_highlight", "row_highlight", "column_highlight"]
            
            for tag in canvas_tags:
                try:
                    items_with_tag = self.trackplan_canvas.find_withtag(tag)
                    if items_with_tag:
                        self.trackplan_canvas.delete(tag)
                except Exception as e:
                    print(f"Erro ao limpar tag '{tag}': {e}")
            try:
                all_items = self.trackplan_canvas.find_all()
                orphan_items = []
                
                for item in all_items:
                    item_tags = self.trackplan_canvas.gettags(item)
                    # Não remover itens da grade (grid, grid_numbers)
                    if not any(tag in ['grid', 'grid_numbers'] for tag in item_tags):
                        orphan_items.append(item)
                
                if orphan_items:
                    for item in orphan_items:
                        try:
                            self.trackplan_canvas.delete(item)
                        except Exception:
                            pass
                            
            except Exception as e:
                print(f"Erro na limpeza forçada: {e}")

            # Limpar seleções e highlights
            if hasattr(self, 'selected_elements'):
                self.clear_selection()

            elements_redrawn = 0
            
            for element in self.trackplan_elements:
                try:
                    self.redraw_element(element)
                    elements_redrawn += 1
                except Exception as e:
                    print(f"Erro ao redesenhar {element.get('type', 'unknown')}: {e}")

            self._restore_rail_visibility_state()
            self._force_hide_auto_rails()

            # Atualizar associações usando a mesma função do undo/redo
            self.update_sensor_fma_associations()
            self.apply_grid()

            switches_after = []
            for i, elem in enumerate(self.trackplan_elements):
                element_type = elem.get('type', 'unknown')
                rail_type = elem.get('rail_type', None)
                if element_type == 'switch' or (element_type == 'rail' and rail_type == 'SWITCH'):
                    switches_after.append((i, elem.get('id'), element_type, rail_type))

            messagebox.showinfo("Sucesso", f"Nova linha inserida acima da linha {row}.\n{moved_elements} elementos foram movidos.")

        except Exception as e:
            error_msg = f"Erro ao inserir linha acima da linha {row}: {e}"
            messagebox.showerror("Erro", error_msg)

    def insert_column_left(self, column):
        """Insere uma nova coluna à esquerda da coluna especificada"""
        try:
            # Salvar estado para undo usando a mesma função do undo/redo
            self.save_state_for_undo()

            # Primeiro, mover todos os elementos que estão na coluna especificada ou à direita
            moved_elements = 0
            elements_to_move = []

            # Coletar elementos que precisam ser movidos
            for element in self.trackplan_elements:
                current_x = element.get('x', -1)
                if current_x >= column:
                    elements_to_move.append(element)

            # Mover cada elemento
            for element in elements_to_move:
                old_x = element['x']
                element['x'] = old_x + 1
                moved_elements += 1

            # Aumentar largura do grid
            current_width = int(self.width_var.get())
            new_width = current_width + 1
            self.width_var.set(str(new_width))
            
            # Limpar por tags específicas
            canvas_tags = ["rail", "link", "sensor", "switch", "fma", "element", 
                        "selection_highlight", "row_highlight", "column_highlight"]
            
            for tag in canvas_tags:
                try:
                    items_with_tag = self.trackplan_canvas.find_withtag(tag)
                    if items_with_tag:
                        self.trackplan_canvas.delete(tag)
                except Exception as e:
                    print(f"Erro ao limpar tag '{tag}': {e}")
            try:
                all_items = self.trackplan_canvas.find_all()
                orphan_items = []
                
                for item in all_items:
                    item_tags = self.trackplan_canvas.gettags(item)
                    # Não remover itens da grade (grid, grid_numbers)
                    if not any(tag in ['grid', 'grid_numbers'] for tag in item_tags):
                        orphan_items.append(item)
                
                if orphan_items:
                    for item in orphan_items:
                        try:
                            self.trackplan_canvas.delete(item)
                        except Exception:
                            pass
                            
            except Exception as e:
                print(f"Erro na limpeza forçada: {e}")

            # Limpar seleções e highlights
            if hasattr(self, 'selected_elements'):
                self.clear_selection()

            elements_redrawn = 0
            
            for element in self.trackplan_elements:
                try:
                    self.redraw_element(element)
                    elements_redrawn += 1
                except Exception as e:
                    print(f"Erro ao redesenhar {element.get('type', 'unknown')}: {e}")

            self._restore_rail_visibility_state()
            self._force_hide_auto_rails()

            # Atualizar associações usando a mesma função do undo/redo
            self.update_sensor_fma_associations()
            self.apply_grid()

            messagebox.showinfo("Sucesso", f"Nova coluna inserida à esquerda da coluna {column}.\n{moved_elements} elementos foram movidos.")

        except Exception as e:
            error_msg = f"Erro ao inserir coluna à esquerda da coluna {column}: {e}"
            messagebox.showerror("Erro", error_msg)
        
    def delete_row(self, row):
        """Remove uma linha inteira"""
        # Confirmar ação
        elements_in_row = [e for e in self.trackplan_elements if e.get('y') == row]
        if elements_in_row:
            response = messagebox.askyesno("Confirmar",
                f"A linha {row} contém {len(elements_in_row)} elemento(s). Deseja remover a linha e todos os elementos?")
            if not response:
                return

        # Salvar estado para undo usando a mesma função do undo/redo
        self.save_state_for_undo()
        for element in elements_in_row:
            try:
                self.delete_element_completely(element)
            except Exception as e:
                print(f"Erro ao remover {element.get('type', 'unknown')}: {e}")

        # Remover da lista trackplan_elements
        self.trackplan_elements = [e for e in self.trackplan_elements if e.get('y') != row]

        # Mover elementos das linhas abaixo para cima
        moved_elements = 0
        for element in self.trackplan_elements:
            if element.get('y', -1) > row:
                element['y'] -= 1
                moved_elements += 1

        # Diminuir altura do grid
        current_height = int(self.height_var.get())
        if current_height > 1:
            new_height = current_height - 1
            self.height_var.set(str(new_height))
        
        # Limpar por tags específicas
        canvas_tags = ["rail", "link", "sensor", "switch", "fma", "element", 
                    "selection_highlight", "row_highlight", "column_highlight"]
        
        for tag in canvas_tags:
            try:
                items_with_tag = self.trackplan_canvas.find_withtag(tag)
                if items_with_tag:
                    self.trackplan_canvas.delete(tag)
            except Exception as e:
                print(f"Erro ao limpar tag '{tag}': {e}")
        try:
            all_items = self.trackplan_canvas.find_all()
            orphan_items = []
            
            for item in all_items:
                item_tags = self.trackplan_canvas.gettags(item)
                # Não remover itens da grade (grid, grid_numbers)
                if not any(tag in ['grid', 'grid_numbers'] for tag in item_tags):
                    orphan_items.append(item)
            
            if orphan_items:
                for item in orphan_items:
                    try:
                        self.trackplan_canvas.delete(item)
                    except Exception:
                        pass
                        
        except Exception as e:
            print(f"Erro na limpeza forçada: {e}")

        # Limpar seleções e highlights
        if hasattr(self, 'selected_elements'):
            self.clear_selection()

        # Redesenhar todos os elementos usando a mesma lógica do restore_state
        elements_redrawn = 0
        
        for element in self.trackplan_elements:
            try:
                self.redraw_element(element)
                elements_redrawn += 1
            except Exception as e:
                print(f"Erro ao redesenhar {element.get('type', 'unknown')}: {e}")

        # Aplicar as mesmas correções do restore_state
        self._restore_rail_visibility_state()
        self._force_hide_auto_rails()

        # Atualizar associações usando a mesma função do undo/redo
        self.update_sensor_fma_associations()

        # Aplicar nova grade
        self.apply_grid()

        messagebox.showinfo("Sucesso", f"Linha {row} removida ({len(elements_in_row)} elementos removidos, {moved_elements} elementos movidos)")
        
    def delete_column(self, column):
        """Remove uma coluna inteira"""
        # Confirmar ação
        elements_in_column = [e for e in self.trackplan_elements if e.get('x') == column]
        if elements_in_column:
            response = messagebox.askyesno("Confirmar",
                f"A coluna {column} contém {len(elements_in_column)} elemento(s). Deseja remover a coluna e todos os elementos?")
            if not response:
                return

        # Salvar estado para undo usando a mesma função do undo/redo
        self.save_state_for_undo()

        # Remover elementos individualmente PRIMEIRO
        for element in elements_in_column:
            try:
                self.delete_element_completely(element)
            except Exception as e:
                print(f"Erro ao remover {element.get('type', 'unknown')}: {e}")

        # Remover da lista trackplan_elements
        self.trackplan_elements = [e for e in self.trackplan_elements if e.get('x') != column]

        # Mover elementos das colunas à direita para a esquerda
        moved_elements = 0
        for element in self.trackplan_elements:
            if element.get('x', -1) > column:
                element['x'] -= 1
                moved_elements += 1

        # Diminuir largura do grid
        current_width = int(self.width_var.get())
        if current_width > 1:
            new_width = current_width - 1
            self.width_var.set(str(new_width))
        
        # Limpar por tags específicas
        canvas_tags = ["rail", "link", "sensor", "switch", "fma", "element", 
                    "selection_highlight", "row_highlight", "column_highlight"]
        
        for tag in canvas_tags:
            try:
                items_with_tag = self.trackplan_canvas.find_withtag(tag)
                if items_with_tag:
                    self.trackplan_canvas.delete(tag)
            except Exception as e:
                print(f"Erro ao limpar tag '{tag}': {e}")
        try:
            all_items = self.trackplan_canvas.find_all()
            orphan_items = []
            
            for item in all_items:
                item_tags = self.trackplan_canvas.gettags(item)
                # Não remover itens da grade (grid, grid_numbers)
                if not any(tag in ['grid', 'grid_numbers'] for tag in item_tags):
                    orphan_items.append(item)
            
            if orphan_items:
                for item in orphan_items:
                    try:
                        self.trackplan_canvas.delete(item)
                    except Exception:
                        pass
                        
        except Exception as e:
            print(f"Erro na limpeza forçada: {e}")

        # Limpar seleções e highlights
        if hasattr(self, 'selected_elements'):
            self.clear_selection()

        # Redesenhar todos os elementos usando a mesma lógica do restore_state
        elements_redrawn = 0
        
        for element in self.trackplan_elements:
            try:
                self.redraw_element(element)
                elements_redrawn += 1
            except Exception as e:
                print(f"Erro ao redesenhar {element.get('type', 'unknown')}: {e}")

        # Aplicar as mesmas correções do restore_state
        self._restore_rail_visibility_state()
        self._force_hide_auto_rails()

        # Atualizar associações usando a mesma função do undo/redo
        self.update_sensor_fma_associations()

        # Aplicar nova grade
        self.apply_grid()

        messagebox.showinfo("Sucesso", f"Coluna {column} removida ({len(elements_in_column)} elementos removidos, {moved_elements} elementos movidos)")

    def copy_column(self, column):
        """Copia uma coluna inteira"""
        # Coletar todos os elementos da coluna
        column_elements = []
        for y in range(int(self.height_var.get()) + 1):
            element_at_position = None
            for element in self.trackplan_elements:
                if element.get('x') == column and element.get('y') == y:
                    element_at_position = element
                    break
            
            if element_at_position:
                element_copy = {
                    'type': element_at_position['type'],
                    'angle': element_at_position.get('angle', 0),
                    'mirror': element_at_position.get('mirror', 0),
                    'name': element_at_position.get('name', ''),
                    'sensors': element_at_position.get('sensors', []).copy(),
                    'rails': element_at_position.get('rails', []).copy(),
                    'position': element_at_position.get('position', 'right'),  # Para sensores
                    'x': 0,  # Será ajustado na colagem
                    'y': y   # Posição relativa na coluna
                }
                column_elements.append(element_copy)
            else:
                # Posição vazia
                column_elements.append(None)
        
        # Salvar no clipboard específico
        self.row_column_clipboard = {
            'type': 'column',
            'data': column_elements
        }
        
        messagebox.showinfo("Sucesso", f"Coluna {column} copiada ({len([e for e in column_elements if e is not None])} elementos)")
    
    def cut_row(self, row):
        """Recorta uma linha inteira"""
        # Primeiro copiar
        self.copy_row(row)
        
        # Depois remover (mas sem diminuir o grid)
        elements_to_remove = [e for e in self.trackplan_elements if e.get('y') == row]
        
        # Salvar estado para undo
        self.save_state_for_undo()
        
        for element in elements_to_remove:
            self.delete_element_completely(element)
            if element in self.trackplan_elements:
                self.trackplan_elements.remove(element)
        
        messagebox.showinfo("Sucesso", f"Linha {row} recortada ({len(elements_to_remove)} elementos)")
    
    def cut_column(self, column):
        """Recorta uma coluna inteira"""
        # Primeiro copiar
        self.copy_column(column)
        
        # Depois remover (mas sem diminuir o grid)
        elements_to_remove = [e for e in self.trackplan_elements if e.get('x') == column]
        
        # Salvar estado para undo
        self.save_state_for_undo()
        
        for element in elements_to_remove:
            self.delete_element_completely(element)
            if element in self.trackplan_elements:
                self.trackplan_elements.remove(element)
        
        messagebox.showinfo("Sucesso", f"Coluna {column} recortada ({len(elements_to_remove)} elementos)")
    
    def paste_row(self, target_row):
        """Cola uma linha inteira"""
        if self.row_column_clipboard['type'] != 'row':
            messagebox.showwarning("Aviso", "Nenhuma linha foi copiada.")
            return
        
        # Salvar estado para undo
        self.save_state_for_undo()
        
        # Remover elementos existentes na linha alvo
        elements_to_remove = [e for e in self.trackplan_elements if e.get('y') == target_row]
        for element in elements_to_remove:
            self.delete_element_completely(element)
            if element in self.trackplan_elements:
                self.trackplan_elements.remove(element)
        
        # Colar elementos da linha copiada
        pasted_count = 0
        row_data = self.row_column_clipboard['data']
        
        for x, element_data in enumerate(row_data):
            if element_data is not None and x < int(self.width_var.get()) + 1:
                # Adicionar elemento baseado no tipo
                new_element = None
                if element_data['type'] == 'rail':
                    new_element = self.add_rail_element(x, target_row, element_data['angle'], element_data['mirror'])
                elif element_data['type'] == 'sensor':
                    new_element = self.add_sensor_element(x, target_row, element_data['angle'])
                elif element_data['type'] == 'switch':
                    new_element = self.add_switch_element(x, target_row, element_data['angle'], element_data['mirror'])
                elif element_data['type'] == 'fma':
                    # Inferir fma_type baseado nos dados salvos ou pelo ID
                    fma_type = element_data.get('fma_type', 'FMA1')
                    if not fma_type:  # Se não tem fma_type, inferir pelo ID
                        element_id = element_data.get('id', '')
                        fma_type = 'FMA2' if str(element_id).startswith('4') else 'FMA1'
                    
                    new_element = self.add_fma_element(x, target_row, element_data['angle'], element_data.get('name', ''), fma_type)
                    if new_element:
                        new_element['sensors'] = element_data.get('sensors', []).copy()
                        new_element['rails'] = element_data.get('rails', []).copy()
                
                if new_element:
                    pasted_count += 1
        
        messagebox.showinfo("Sucesso", f"Linha colada na linha {target_row} ({pasted_count} elementos)")
    
    def paste_column(self, target_column):
        """Cola uma coluna inteira"""
        if self.row_column_clipboard['type'] != 'column':
            messagebox.showwarning("Aviso", "Nenhuma coluna foi copiada.")
            return
        
        # Salvar estado para undo
        self.save_state_for_undo()
        
        # Remover elementos existentes na coluna alvo
        elements_to_remove = [e for e in self.trackplan_elements if e.get('x') == target_column]
        for element in elements_to_remove:
            self.delete_element_completely(element)
            if element in self.trackplan_elements:
                self.trackplan_elements.remove(element)
        
        # Colar elementos da coluna copiada
        pasted_count = 0
        column_data = self.row_column_clipboard['data']
        
        for y, element_data in enumerate(column_data):
            if element_data is not None and y < int(self.height_var.get()) + 1:
                # Adicionar elemento baseado no tipo
                new_element = None
                if element_data['type'] == 'rail':
                    new_element = self.add_rail_element(target_column, y, element_data['angle'], element_data['mirror'])
                elif element_data['type'] == 'sensor':
                    new_element = self.add_sensor_element(target_column, y, element_data['angle'])
                elif element_data['type'] == 'switch':
                    new_element = self.add_switch_element(target_column, y, element_data['angle'], element_data['mirror'])
                elif element_data['type'] == 'fma':
                    # Inferir fma_type baseado nos dados salvos ou pelo ID
                    fma_type = element_data.get('fma_type', 'FMA1')
                    if not fma_type:  # Se não tem fma_type, inferir pelo ID
                        element_id = element_data.get('id', '')
                        fma_type = 'FMA2' if str(element_id).startswith('4') else 'FMA1'
                    
                    new_element = self.add_fma_element(target_column, y, element_data['angle'], element_data.get('name', ''), fma_type)
                    if new_element:
                        new_element['sensors'] = element_data.get('sensors', []).copy()
                        new_element['rails'] = element_data.get('rails', []).copy()
                
                if new_element:
                    pasted_count += 1
        
        messagebox.showinfo("Sucesso", f"Coluna colada na coluna {target_column} ({pasted_count} elementos)")

    def clear_trackplan(self):
        """Limpa todo o trackplan de forma completa"""
        response = messagebox.askyesno("Confirmar", "Deseja limpar todo o trackplan?")
        if response:
            self.save_state_for_undo()
        
            # Limpar elementos individualmente ANTES de limpar canvas
            removed_count = 0
            for element in list(self.trackplan_elements):  # Usar list() para evitar modificação durante iteração
                element_type = element.get('type', 'unknown')
                try:
                    self.delete_element_completely(element)
                    removed_count += 1
                except Exception as e:
                    print(f"Erro ao remover {element_type}: {e}")
                        
            # Limpar TODAS as tags possíveis do canvas (incluindo tags específicas de FMA)
            tags_to_clear = ["rail", "link", "sensor", "switch", "fma", "element", 
                            "selection_highlight", "row_highlight", "column_highlight"]
            
            for tag in tags_to_clear:
                try:
                    items_deleted = len(self.trackplan_canvas.find_withtag(tag))
                    self.trackplan_canvas.delete(tag)
                except Exception as e:
                    print(f"Erro ao limpar tag '{tag}': {e}")
            
            # Limpeza de qualquer item restante no canvas
            try:
                all_items = self.trackplan_canvas.find_all()
                for item in all_items:
                    item_tags = self.trackplan_canvas.gettags(item)
                    # Não remover itens da grade (grid, grid_numbers)
                    if not any(tag in ['grid', 'grid_numbers'] for tag in item_tags):
                        try:
                            self.trackplan_canvas.delete(item)
                        except Exception:
                            pass
            except Exception as e:
                print(f"Erro na limpeza forçada: {e}")
            
            # Limpar lista de elementos
            self.trackplan_elements.clear()
            
            # Limpar seleção
            self.clear_all_highlights()
            
            # Resetar ID counter
            self.next_element_id = 7000
            self.next_sensor_id = 2000
            self.next_fma_id = 3000
            
            # Limpar registry de imagens para liberar memória
            self.clear_image_registry()
            
            # Remove nome do Trackplan
            if hasattr(self, 'trackplan_fds_name_var'):
                self.trackplan_fds_name_var.set("Trackplan - Carregue um Trackplan.xml ou configure um nome na aba de Configuração FDS")
            
            messagebox.showinfo("Sucesso", "Trackplan limpo completamente.")
    
    def load_element_images(self):
        """Carrega imagens dos elementos se disponíveis"""
        self.element_images = {}
        self.blue_element_images = {}  # Imagens azuis para destacamento
        try:
            from PIL import Image, ImageTk
            import os
            
            # Diretório de imagens (criar pasta 'images' no mesmo diretório do script)
            images_dir = os.path.join(os.path.dirname(__file__), "images")
            blue_images_dir = os.path.join(images_dir, "blue")  # Pasta para imagens azuis
            
            if os.path.exists(images_dir):
                # Usar o tamanho completo do grid para pixel art fidedigna
                image_size = self.grid_size  # 30x30 pixels completos
                
                # Lista completa de imagens a carregar
                image_files = {}
                
                # RAILS - Combinações corretas de ângulo e mirror
                rail_angles = [0, 45, 90, 180, 225, 270, 315]
                for angle in rail_angles:
                        for mirror in [0, 1]:
                            key = f"rail_{angle}_{mirror}"
                            filename = f"rail_{angle}_{mirror}.png"
                            image_files[key] = filename
                # LINKS
                link_angles = [0, 90, 180, 270]
                for angle in link_angles:
                    key = f"link_{angle}"
                    filename = f"link_{angle}.png"
                    image_files[key] = filename

                # CROSSING Ângulos 0/90/270 
                for angle in [0, 90, 270]:
                    key = f"crossing_{angle}"
                    filename = f"crossing_{angle}.png"
                    image_files[key] = filename

                # SWITCHES - Todas as combinações de ângulo e mirror
                switch_angles = [0, 45, 90, 180, 225]
                for angle in switch_angles:
                    for mirror in [0, 1]:
                        key = f"switch_{angle}_{mirror}"
                        filename = f"switch_{angle}_{mirror}.png"
                        image_files[key] = filename
                
                # SENSORES - Ângulos padrão (sem direção para imagens normais)
                sensor_angles = [0, 45, 90, 135, 180, 225, 270, 315]
                for angle in sensor_angles:
                    key = f"sensor_{angle}"
                    filename = f"sensor_{angle}.png"
                    image_files[key] = filename
                
                # Carregar todas as imagens NORMAIS
                loaded_count = 0
                for key, filename in image_files.items():
                    image_path = os.path.join(images_dir, filename)
                    if os.path.exists(image_path):
                        try:
                            # Carregar e redimensionar imagem
                            img = Image.open(image_path)
                            img = img.resize((image_size, image_size), Image.Resampling.LANCZOS)
                            # Criar PhotoImage com correção de bug Python 3.13
                            self.element_images[key] = self.create_safe_photo_image(img, f"element_{key}")
                            if self.element_images[key]:  # Só contar se criou com sucesso
                                loaded_count += 1
                        except Exception as e:
                            print(f"Erro ao carregar imagem {filename}: {e}")
                
                # Carregar todas as imagens AZUIS (da pasta images/blue/)
                blue_loaded_count = 0
                if os.path.exists(blue_images_dir):
                    # Para rails, switches e FMAs - usar mesma estrutura das imagens normais
                    for key, filename in image_files.items():
                        # Buscar imagem azul correspondente
                        blue_image_path = os.path.join(blue_images_dir, filename)
                        if os.path.exists(blue_image_path):
                            try:
                                # Carregar e redimensionar imagem azul
                                img = Image.open(blue_image_path)
                                img = img.resize((image_size, image_size), Image.Resampling.LANCZOS)
                                # Criar PhotoImage com correção de bug Python 3.13
                                self.blue_element_images[key] = self.create_safe_photo_image(img, f"blue_element_{key}")
                                if self.blue_element_images[key]:  # Só contar se criou com sucesso
                                    blue_loaded_count += 1
                            except Exception as e:
                                print(f"Erro ao carregar imagem azul {filename}: {e}")
                    
                # Para SENSORES AZUIS - usar sistema left/right
                sensor_blue_expected = 0
                for angle in sensor_angles:
                    for direction in ['left', 'right']:
                        blue_key = f"sensor_{angle}_{direction}"
                        blue_filename = f"sensor_{angle}_{direction}.png"
                        blue_image_path = os.path.join(blue_images_dir, blue_filename)
                        sensor_blue_expected += 1
                        if os.path.exists(blue_image_path):
                            try:
                                # Carregar e redimensionar imagem azul do sensor
                                img = Image.open(blue_image_path)
                                img = img.resize((image_size, image_size), Image.Resampling.LANCZOS)
                                # Criar PhotoImage com correção de bug Python 3.13
                                self.blue_element_images[blue_key] = self.create_safe_photo_image(img, f"blue_sensor_{blue_key}")
                                if self.blue_element_images[blue_key]:  # Só contar se criou com sucesso
                                    blue_loaded_count += 1
                            except Exception as e:
                                print(f"Erro ao carregar imagem azul de sensor {blue_filename}: {e}")
                        else:
                            print("Pasta de imagens azuis não encontrada. Criando...")
                            os.makedirs(blue_images_dir, exist_ok=True)
                    sensor_blue_expected = len(sensor_angles) * 2  # left/right para cada ângulo
                
                # GERAR IMAGENS FMA DINAMICAMENTE PARA PREVIEW
                # Implementando a ideia do usuário: criar FMAs com texto "FMA" durante o carregamento
                fma_preview_count = 0
                fma_angles = [0, 90, 180, 270]
                for angle in fma_angles:
                    preview_key = f"fma_{angle}_PREV"
                    try:
                        dynamic_image = self.create_fma_image_with_integrated_text(angle, "FMA")
                        if dynamic_image:
                            self.element_images[preview_key] = dynamic_image
                            fma_preview_count += 1
                        else:
                            print(f"Falha ao criar: {preview_key}")
                    except Exception as e:
                        print(f"Erro ao criar {preview_key}: {e}")
                
                # Listar imagens faltantes para facilitar a criação
                missing_images = []
                missing_blue_images = []
                
                # Verificar imagens normais faltantes
                for key, filename in image_files.items():
                    image_path = os.path.join(images_dir, filename)
                    if not os.path.exists(image_path):
                        missing_images.append(filename)
                
                # Verificar imagens azuis faltantes (rails, switches, FMAs)
                for key, filename in image_files.items():
                    blue_image_path = os.path.join(blue_images_dir, filename)
                    if not os.path.exists(blue_image_path):
                        missing_blue_images.append(filename)
                
                # Verificar imagens azuis de sensores faltantes (sistema left/right)
                for angle in sensor_angles:
                    for direction in ['left', 'right']:
                        blue_sensor_filename = f"sensor_{angle}_{direction}.png"
                        blue_sensor_path = os.path.join(blue_images_dir, blue_sensor_filename)
                        if not os.path.exists(blue_sensor_path):
                            missing_blue_images.append(blue_sensor_filename)
                        
            else:
                print(f"Diretorio de imagens nao encontrado: {images_dir}")
                print("Criando estrutura de pastas...")
                os.makedirs(images_dir, exist_ok=True)
                os.makedirs(blue_images_dir, exist_ok=True)
                
        except ImportError:
            print("PIL nao encontrado. Execute: pip install Pillow")
            print("Usando desenho por linhas...")
        except Exception as e:
            print(f"Erro ao carregar imagens: {e}")
    
    def set_tool_shortcut(self, tool):
        """Define a ferramenta usando atalho de teclado"""
        try:
            if hasattr(self, 'tool_var'):
                self.tool_var.set(tool)
                
                # Atualizar opções de ângulo conforme a ferramenta
                self.update_angle_options()
                
                # Atualizar preview visual
                self.update_tool_preview()
        except Exception as e:
            print(f"Erro ao definir ferramenta: {e}")
    
    def on_mouse_wheel(self, event):
        """Gerencia rotação do mouse wheel para alterar ângulos"""
        # Verificar se estamos em modo de seleção ou borracha (não altera ângulos)
        current_tool = self.tool_var.get()
        if current_tool in ["select", "eraser"]:
            return
        
        # Determinar direção da rotação
        if event.delta > 0:  # Roda para cima
            self.rotate_angle_forward()
        else:  # Roda para baixo
            self.rotate_angle_backward()
        
        # Atualizar preview visual
        self.update_tool_preview()
    
    def rotate_angle_forward(self):
        """Rotaciona o ângulo para frente na sequência"""
        current_tool = self.tool_var.get()
        current_angle = int(self.angle_var.get())
        
        # Definir ângulos disponíveis por ferramenta
        angles_by_tool = {
            "rail": [0, 45, 90, 180, 225, 270, 315],
            "sensor": [0, 45, 90, 135, 180, 225, 270, 315],
            "switch": [0, 45, 90, 180, 225],
            "fma": [0, 90, 180, 270],
            "link": [0, 90, 180, 270],
            "crossing": [0, 90 ,270]
        }
        
        if current_tool in angles_by_tool:
            available_angles = angles_by_tool[current_tool]
            try:
                current_index = available_angles.index(current_angle)
                next_index = (current_index + 1) % len(available_angles)
                new_angle = available_angles[next_index]
                self.angle_var.set(str(new_angle))
            except ValueError:
                # Se o ângulo atual não estiver na lista, usar o primeiro
                self.angle_var.set(str(available_angles[0]))
    
    def rotate_angle_backward(self):
        """Rotaciona o ângulo para trás na sequência"""
        current_tool = self.tool_var.get()
        current_angle = int(self.angle_var.get())
        
        # Definir ângulos disponíveis por ferramenta
        angles_by_tool = {
            "rail": [0, 45, 90, 180, 225, 270, 315],
            "sensor": [0, 45, 90, 135, 180, 225, 270, 315],
            "switch": [0, 45, 90, 180, 225],
            "fma": [0, 90, 180, 270],
            "link": [0, 90, 180, 270],
            "crossing": [0, 90, 270]
        }
        
        if current_tool in angles_by_tool:
            available_angles = angles_by_tool[current_tool]
            try:
                current_index = available_angles.index(current_angle)
                prev_index = (current_index - 1) % len(available_angles)
                new_angle = available_angles[prev_index]
                self.angle_var.set(str(new_angle))
            except ValueError:
                # Se o ângulo atual não estiver na lista, usar o último
                self.angle_var.set(str(available_angles[-1]))
    
    def create_fma_image_with_integrated_text(self, angle, text):
        """
        Cria uma imagem FMA personalizada com texto integrado nas posições especificadas
        
        Args:
            angle: Ângulo da FMA (0, 90, 180, 270)  
            text: Texto a ser integrado na imagem (ex: "2DAT", "1AT", etc)
            
        Returns:
            ImageTk.PhotoImage pronto para uso no canvas ou None se erro
        """
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageTk
            
            # Criar imagem 30x30 com fundo transparente
            img = Image.new('RGBA', (30, 30), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Definir posições dos quadrados de texto por ângulo - AJUSTADO POR ORIENTAÇÃO
            text_areas = {
                0: {'x1': 2, 'y1': 18, 'x2': 29, 'y2': 28, 'rotation': 0},     # Ângulo 0° (subiu 1 pixel)
                90: {'x1': 18, 'y1': 2, 'x2': 28, 'y2': 29, 'rotation': 90},   # Ângulo 90° (esquerda 1 pixel)
                180: {'x1': 2, 'y1': 3, 'x2': 29, 'y2': 13, 'rotation': 180},  # Ângulo 180° (desceu 1 pixel)
                270: {'x1': 3, 'y1': 2, 'x2': 13, 'y2': 29, 'rotation': 270}   # Ângulo 270° (direita 1 pixel)
            }
            
            if angle not in text_areas:
                angle = 0  # Fallback para ângulo 0
            
            area = text_areas[angle]
            
            # Desenhar linha principal baseada no ângulo - AJUSTADO 1 pixel para cima
            if angle == 0:
                # Linha horizontal: x=1,y=13 até x=29,y=17
                for y in range(13, 17):
                    draw.line([(1, y), (29, y)], fill=(0, 0, 0, 255), width=1)
            elif angle == 90:
                # Linha vertical equivalente: x=13,y=0 até x=17,y=29
                for x in range(13, 17):
                    draw.line([(x, 1), (x, 29)], fill=(0, 0, 0, 255), width=1)
            elif angle == 180:
                # Linha horizontal invertida: x=1,y=13 até x=29,y=17
                for y in range(13, 17):
                    draw.line([(1, y), (29, y)], fill=(0, 0, 0, 255), width=1)
            elif angle == 270:
                # Linha vertical invertida: x=13,y=1 até x=17,y=29
                for x in range(13, 17):
                    draw.line([(x, 1), (x, 29)], fill=(0, 0, 0, 255), width=1)

            # Desenhar quadrado de texto
            draw.rectangle([
                (area['x1'], area['y1']),
                (area['x2'], area['y2'])
            ], outline=(0, 0, 0, 255), width=1, fill=(255, 255, 255, 255))  # Fundo branco para o texto
            
            # Adicionar texto no quadrado
            try:
                font = ImageFont.truetype("arial.ttf", 4, bold=True)  # Fonte menor para FMAs
            except:
                font = ImageFont.load_default()
            
            # Calcular centro do quadrado de texto (toda FMA já foi ajustada 1 pixel para cima)
            text_center_x = (area['x1'] + area['x2']) // 2
            text_center_y = (area['y1'] + area['y2']) // 2  # Centro normal, pois toda FMA subiu
            
            # Para ângulos 90° e 270°, criar texto rotacionado
            if angle == 90:
                # Criar imagem temporária para rotacionar o texto
                temp_img = Image.new('RGBA', (50, 50), (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.text((25, 25), text, fill=(0, 0, 0, 255), font=font, anchor="mm")
                temp_img = temp_img.rotate(-90, expand=False)  # Rotacionar 90° horário
                # Colar texto rotacionado na posição correta
                img.paste(temp_img, (text_center_x - 25, text_center_y - 25), temp_img)
            elif angle == 270:
                # Criar imagem temporária para rotacionar o texto
                temp_img = Image.new('RGBA', (50, 50), (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.text((25, 25), text, fill=(0, 0, 0, 255), font=font, anchor="mm")
                temp_img = temp_img.rotate(90, expand=False)  # Rotacionar 90° anti-horário
                # Colar texto rotacionado na posição correta
                img.paste(temp_img, (text_center_x - 25, text_center_y - 25), temp_img)
            else:
                # Texto normal (0° e 180°)
                draw.text((text_center_x, text_center_y), text, fill=(0, 0, 0, 255), font=font, anchor="mm")
            
            # Converter para ImageTk.PhotoImage com correção de bug Python 3.13
            return self.create_safe_photo_image(img, f"fma_{angle}_{text}")
            
        except Exception as e:
            print(f"Erro ao criar imagem FMA com texto '{text}' (ângulo {angle}°): {e}")
            return None
    
    def create_fma_blue_image_with_integrated_text(self, angle, text):
        """
        Cria uma imagem FMA AZUL personalizada com texto integrado (para highlighting)
        
        Args:
            angle: Ângulo da FMA (0, 90, 180, 270)  
            text: Texto a ser integrado na imagem (ex: "2DAT", "1AT", etc)
            
        Returns:
            ImageTk.PhotoImage azul pronto para uso no canvas ou None se erro
        """
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageTk
            
            # Criar imagem 30x30 com fundo transparente
            img = Image.new('RGBA', (30, 30), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Definir posições dos quadrados de texto por ângulo - AJUSTADO 1 pixel para cima
            text_areas = {
                0: {'x1': 2, 'y1': 18, 'x2': 29, 'y2': 28, 'rotation': 0},     # Ângulo 0°
                90: {'x1': 18, 'y1': 2, 'x2': 28, 'y2': 29, 'rotation': 90},   # Ângulo 90°
                180: {'x1': 2, 'y1': 3, 'x2': 29, 'y2': 13, 'rotation': 180},  # Ângulo 180°
                270: {'x1': 3, 'y1': 2, 'x2': 13, 'y2': 29, 'rotation': 270}   # Ângulo 270°
            }
            
            if angle not in text_areas:
                angle = 0  # Fallback para ângulo 0
            
            area = text_areas[angle]
            
            # CORES AZUIS para highlighting
            blue_line_color = (48, 48, 227, 255)      # Azul para linhas
            blue_outline_color = (48, 48, 227, 255)   # Azul para contorno
            blue_fill_color = (255, 255, 255, 255)    # Fundo BRANCO para a caixa de texto (igual às FMAs normais)
            blue_text_color = (0, 0, 0, 255)          # Texto PRETO para legibilidade no fundo branco
            
            # Desenhar linha principal baseada no ângulo - AJUSTADO 1 pixel para cima
            if angle == 0:
                # Linha horizontal: x=1,y=13 até x=29,y=17
                for y in range(13, 17):
                    draw.line([(1, y), (29, y)], fill=blue_line_color, width=1)
            elif angle == 90:
                # Linha vertical equivalente: x=13,y=0 até x=17,y=29
                for x in range(13, 17):
                    draw.line([(x, 1), (x, 29)], fill=blue_line_color, width=1)
            elif angle == 180:
                # Linha horizontal invertida: x=1,y=13 até x=29,y=17
                for y in range(13, 17):
                    draw.line([(1, y), (29, y)], fill=blue_line_color, width=1)
            elif angle == 270:
                # Linha vertical invertida: x=13,y=1 até x=17,y=29
                for x in range(13, 17):
                    draw.line([(x, 1), (x, 29)], fill=blue_line_color, width=1)

            # Desenhar quadrado de texto (EM AZUL)
            draw.rectangle([
                (area['x1'], area['y1']),
                (area['x2'], area['y2'])
            ], outline=blue_outline_color, width=1, fill=blue_fill_color)  # Fundo azul claro para o texto
            
            # Adicionar texto no quadrado (EM AZUL ESCURO)
            try:
                font = ImageFont.truetype("arial.ttf", 4, bold=True)  # Fonte menor para FMAs
            except:
                font = ImageFont.load_default()
            
            # Calcular centro do quadrado de texto (toda FMA já foi ajustada 1 pixel para cima)
            text_center_x = (area['x1'] + area['x2']) // 2
            text_center_y = (area['y1'] + area['y2']) // 2  # Centro normal, pois toda FMA subiu
            
            # Para ângulos 90° e 270°, criar texto rotacionado
            if angle == 90:
                # Criar imagem temporária para rotacionar o texto
                temp_img = Image.new('RGBA', (50, 50), (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.text((25, 25), text, fill=blue_text_color, font=font, anchor="mm")
                temp_img = temp_img.rotate(-90, expand=False)  # Rotacionar 90° horário
                # Colar texto rotacionado na posição correta
                img.paste(temp_img, (text_center_x - 25, text_center_y - 25), temp_img)
            elif angle == 270:
                # Criar imagem temporária para rotacionar o texto
                temp_img = Image.new('RGBA', (50, 50), (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.text((25, 25), text, fill=blue_text_color, font=font, anchor="mm")
                temp_img = temp_img.rotate(90, expand=False)  # Rotacionar 90° anti-horário
                # Colar texto rotacionado na posição correta
                img.paste(temp_img, (text_center_x - 25, text_center_y - 25), temp_img)
            else:
                # Texto normal (0° e 180°)
                draw.text((text_center_x, text_center_y), text, fill=blue_text_color, font=font, anchor="mm")
            
            # Converter para ImageTk.PhotoImage com correção de bug Python 3.13
            return self.create_safe_photo_image(img, f"fma_blue_{angle}_{text}")
            
        except Exception as e:
            print(f"Erro ao criar imagem FMA AZUL com texto '{text}' (ângulo {angle}°): {e}")
            return None
    
    def load_trackplan(self, filename=None):
        """Carrega um trackplan XML de forma organizada e eficiente"""
        if filename is None:
            filename = filedialog.askopenfilename(
                title="Carregar Trackplan.xml",
                defaultextension=".xml",
                filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
            )

        if not filename:
            return

        try:
            # String de caminho
            if isinstance(filename, str):
                tree = ET.parse(filename)

            # Bytes (conteúdo vindo do zip)
            elif isinstance(filename, bytes):
                tree = ET.ElementTree(ET.fromstring(filename))

            # File-like object
            else:
                tree = ET.parse(filename)

            root = tree.getroot()
            
            # Estrutura de dados organizada
            
            xml_data = TrackplanXMLData(root, getattr(filename, 'name', 'from_zip'))
            
            # Limpar estado atual
            self._clear_current_trackplan()
            
            # Aplicar configurações
            self._apply_trackplan_dimensions(xml_data)
            
            # Carregar elementos em ordem específica
            self._load_rails_switches_and_links(xml_data)
            self._load_sensors_simplified(xml_data)
            self._load_fmas_simplified(xml_data)
            
            # Atualizar next_element_id baseado nos elementos carregados
            self._update_next_element_id_from_loaded_elements()

            # Finalizar carregamento
            self._finalize_trackplan_loading(xml_data, filename)
            
            self.refresh_fma_test_window()
        except Exception as e:
            self._handle_loading_error(e)

    def load_fds_recovery(self):
        """Carrega o FdsRecovery.zip para análise de um projeto completo"""
        try:
            filename = filedialog.askopenfilename(
                title="Carregar FdsRecovery.zip",
                defaultextension=".zip",
                filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
            )

            if not filename:
                return

            with zipfile.ZipFile(filename, 'r') as zip_ref:
                xml_files = [f for f in zip_ref.namelist() if f.endswith(".xml")]

                for xml_name in xml_files:
                    with zip_ref.open(xml_name) as f:
                        conteudoxml = f.read()
                        if "FdsConfig" in xml_name:
                            self.load_fds_config(conteudoxml)

                        elif "Trackplan" in xml_name:
                            self.load_trackplan(conteudoxml)
                            self.load_cubicles_from_xml(conteudoxml)

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar FdsRecovery.zip: {e}")
            

    def _strip_prefix(self, raw_id: str):
        """Remove prefixos de tipo (2=sensor,3/4=FMA) para cálculo de base."""
        s = str(raw_id)
        if len(s) > 1 and s[0] in ('2', '3', '4'):
            tail = s[1:]
            if tail.isdigit():
                return int(tail)
        # Fallback: se for inteiro simples
        try:
            return int(s)
        except:
            return None

    def _update_next_element_id_from_loaded_elements(self):
        """Atualiza next_element_id usando apenas bases numéricas (sem prefixos de tipo)."""
        try:
            max_base = 0
            for e in self.trackplan_elements:
                eid = e.get('id')
                base = self._strip_prefix(eid)
                if base is not None and base > max_base:
                    max_base = base
            # Não misturar com elementos FDS (mantenha escopos separados)
            self.next_element_id = max_base + 1 if max_base > 0 else 7000
        except Exception as ex:
            print(f"Falha ao recalcular next_element_id: {ex}")
            self.next_element_id = 7000

    def _get_trackplan_filename(self):
        """Obtém o nome do arquivo de trackplan para carregar"""
        return filedialog.askopenfilename(
            title="Carregar Trackplan XML",
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
    
    def _clear_current_trackplan(self):
        """Limpa o trackplan atual com limpeza robusta"""

        # Remover elementos individualmente PRIMEIRO ***
        for element in list(self.trackplan_elements):  # Usar list() para evitar modificação durante iteração
            element_type = element.get('type', 'unknown')
            try:
                self.delete_element_completely(element)
            except Exception as e:
                print(f"Erro ao remover {element_type}: {e}")
        
        # Limpar por tags específicas
        canvas_tags = ["rail", "link", "crossing", "sensor", "switch", "fma", "element", 
                    "selection_highlight", "row_highlight", "column_highlight"]
        
        for tag in canvas_tags:
            try:
                items_with_tag = self.trackplan_canvas.find_withtag(tag)
                if items_with_tag:
                    self.trackplan_canvas.delete(tag)
            except Exception as e:
                print(f"Erro ao limpar tag '{tag}': {e}")
        try:
            all_items = self.trackplan_canvas.find_all()
            orphan_items = []
            
            for item in all_items:
                item_tags = self.trackplan_canvas.gettags(item)
                # Não remover itens da grade (grid, grid_numbers)
                if not any(tag in ['grid', 'grid_numbers'] for tag in item_tags):
                    orphan_items.append(item)
            
            if orphan_items:
                for item in orphan_items:
                    try:
                        self.trackplan_canvas.delete(item)
                    except Exception:
                        pass
                        
        except Exception as e:
            print(f"Erro na limpeza forçada: {e}")

        # Limpar seleções e highlights
        if hasattr(self, 'selected_elements'):
            self.clear_selection()

        self.clear_image_registry()
        
        # Limpar dados
        self.trackplan_elements.clear()
        self.next_element_id = 7000
            
    def _apply_trackplan_dimensions(self, xml_data):
        """Aplica as dimensões do trackplan à grade"""
        track_elem = xml_data.root.find(".//Track")

        width_val = None
        height_val = None

        if track_elem is not None:
            w_attr = track_elem.get("width")
            h_attr = track_elem.get("height")
            # Tentar converter atributos para int
            try:
                if w_attr is not None and str(w_attr).strip() != "":
                    width_val = int(str(w_attr).strip())
            except Exception:
                width_val = None
            try:
                if h_attr is not None and str(h_attr).strip() != "":
                    height_val = int(str(h_attr).strip())
            except Exception:
                height_val = None

            # Fallback: calcular a partir dos elementos, se necessário
            if width_val is None or height_val is None:
                max_x = -1
                max_y = -1
                try:
                    if xml_data.rails:
                        max_x = max(max_x, max(r.x for r in xml_data.rails))
                        max_y = max(max_y, max(r.y for r in xml_data.rails))
                    if xml_data.sensors:
                        max_x = max(max_x, max(s.x for s in xml_data.sensors))
                        max_y = max(max_y, max(s.y for s in xml_data.sensors))
                    if xml_data.fmas:
                        max_x = max(max_x, max(f.x for f in xml_data.fmas))
                        max_y = max(max_y, max(f.y for f in xml_data.fmas))
                except Exception as e:
                    print(f"Falha ao calcular dimensões pelo conteúdo: {e}")

                if width_val is None and max_x >= 0:
                    width_val = max_x
                if height_val is None and max_y >= 0:
                    height_val = max_y

            # Defaults finais se ainda não definidos
            if width_val is None:
                width_val = 71
            if height_val is None:
                height_val = 16

            self.width_var.set(str(width_val))
            self.height_var.set(str(height_val))
            self.apply_grid()
        else:
            print("Elemento Track não encontrado, usando dimensões padrão 71x16")
            self.width_var.set("71")
            self.height_var.set("16")
            self.apply_grid()
    
    def _load_rails_switches_and_links(self, xml_data):
        """Carrega todos os rails e switches do XML preservando IDs originais"""        
        for rail_data in xml_data.rails:
            try:
                if rail_data.rail_type == "SWITCH":
                    element = self.add_switch_element(rail_data.x, rail_data.y, rail_data.angle, rail_data.mirror)
                else:
                    element = self.add_rail_element(rail_data.x, rail_data.y, rail_data.angle, rail_data.mirror)
                ''
                # *** MELHORADO: Preservar ID original do XML ***
                if rail_data.rail_id:
                    try:
                        # Tentar converter para int primeiro
                        original_id = int(rail_data.rail_id)
                        element['id'] = original_id
                        element['xml_id'] = rail_data.rail_id
                    except ValueError:
                        # Se não for numérico, manter como string
                        element['id'] = rail_data.rail_id
                        element['xml_id'] = rail_data.rail_id                
            except Exception as e:
                print(f"Erro ao carregar rail {rail_data.rail_id}: {e}")

        for crossing_data in xml_data.crossings:
            try:
                element = self.add_crossing_element(crossing_data.x, crossing_data.y, crossing_data.angle)
                if crossing_data.crossing_id:
                    try:
                        original_id = int(crossing_data.crossing_id)
                        element['id'] = original_id
                        element['xml_id'] = crossing_data.crossing_id
                    except ValueError:
                        element['id'] = crossing_data.crossing_id
                        element['xml_id'] = crossing_data.crossing_id
                        
            except Exception as e:
                print(f"Erro ao carregar crossing {crossing_data.crossing_id}: {e}")

        for link_data in xml_data.links:
            try:
                element = self.add_link_element(link_data.x, link_data.y, link_data.angle, link_data.url)
                
                # Preservar ID original do XML
                if link_data.link_id:
                    try:
                        original_id = int(link_data.link_id)
                        element['id'] = original_id
                        element['xml_id'] = link_data.link_id
                    except ValueError:
                        element['id'] = link_data.link_id
                        element['xml_id'] = link_data.link_id
                        
            except Exception as e:
                print(f"Erro ao carregar link {link_data.link_id}: {e}")
            
    def _load_sensors_simplified(self, xml_data):
        """Carrega sensores sem phantom rails - apenas elementos visuais"""
        for sensor_data in xml_data.sensors:
            try:
                # Criar elemento sensor visualmente apenas
                element = self.add_sensor_element(sensor_data.x, sensor_data.y, sensor_data.angle)
                element['name'] = sensor_data.name
                element['ref_id'] = sensor_data.ref_id
                element['xml_id'] = sensor_data.sensor_id

                if getattr(sensor_data, "fma0", None):
                    element['fma0'] = str(sensor_data.fma0)

                if getattr(sensor_data, "fma1", None):
                    element['fma1'] = str(sensor_data.fma1)
                
                # *** MELHORADO: Preservar ID original do XML ***
                if sensor_data.sensor_id:
                    try:
                        original_id = int(sensor_data.sensor_id)
                        element['id'] = original_id
                    except ValueError:
                        element['id'] = sensor_data.sensor_id                
                
                # Verificar se há rail real na mesma posição
                position = (sensor_data.x, sensor_data.y)
                existing_rail = self._find_rail_at_position(position)
                
                if existing_rail:
                    # Apenas esconder visualmente o rail existente
                    self._hide_rail_visual(existing_rail)
                
            except Exception as e:
                print(f"Erro ao carregar sensor {sensor_data.sensor_id}: {e}")
            
    def _load_fmas_simplified(self, xml_data):
        """Carrega FMAs preservando IDs originais"""        
        fmas_loaded = 0
        
        for fma_data in xml_data.fmas:
            try:
                # Inferir fma_type baseado no ID da FMA
                fma_type = 'FMA2' if str(fma_data.fma_id).startswith('4') else 'FMA1'
                
                # Criar elemento FMA
                element = self.add_fma_element(fma_data.x, fma_data.y, fma_data.angle, fma_data.name, fma_type)
                element['xml_id'] = fma_data.fma_id
                element['ref_id'] = fma_data.ref_id
                
                # Preservar ID original do XML
                if fma_data.fma_id:
                    try:
                        original_id = int(fma_data.fma_id)
                        element['id'] = original_id
                    except ValueError:
                        element['id'] = fma_data.fma_id
                
                # Verificar se há rail real na mesma posição
                position = (fma_data.x, fma_data.y)
                existing_rail = self._find_rail_at_position(position)
                
                if existing_rail:
                    # Apenas esconder visualmente o rail existente
                    self._hide_rail_visual(existing_rail)
                
                # Carregar associações (preservar para XML inteligente)
                element['associated_sensors'] = fma_data.associated_sensors
                element['associated_rails'] = fma_data.associated_rails
                
                fmas_loaded += 1
                
            except Exception as e:
                print(f"Erro ao carregar FMA {fma_data.fma_id}: {e}")
        
        return fmas_loaded
    
    def _finalize_trackplan_loading(self, xml_data, filename):
        """Finaliza o carregamento do trackplan com redesenho robusto"""
        
        # Limpar por tags específicas novamente (por segurança)
        canvas_tags = ["rail", "link", "sensor", "switch", "fma", "element", 
                    "selection_highlight", "row_highlight", "column_highlight"]
        
        for tag in canvas_tags:
            try:
                items_with_tag = self.trackplan_canvas.find_withtag(tag)
                if items_with_tag:
                    self.trackplan_canvas.delete(tag)
            except Exception as e:
                print(f"Erro na limpeza final tag '{tag}': {e}")

        elements_redrawn = 0
        
        for element in self.trackplan_elements:
            try:
                self.redraw_element(element)
                elements_redrawn += 1
            except Exception as e:
                print(f"Erro ao redesenhar {element.get('type', 'unknown')}: {e}")

        self._restore_rail_visibility_state()
        self._force_hide_auto_rails()        
        # Atualizar associações
        self.update_sensor_fma_associations()
        
        # Armazenar dados para correlação
        self.trackplan_data = {
            'root': xml_data.root,
            'filename': filename,
            'fmas': xml_data.fmas_dict,
            'sensors': xml_data.sensors_dict,
            'rails': xml_data.rails_dict,
            'links': xml_data.links_dict,
        }
        
        # Aplicar grade após carregamento 
        self.apply_grid()

        # Atualizar nome do FDS baseado no Trackplan.xml carregado
        self.update_trackplan_fds_name()
        
        # Mostrar resultado
        fma_count = len(xml_data.fmas)
        messagebox.showinfo("Sucesso", f"Trackplan XML carregado! \n{fma_count} FMAs carregadas com sucesso!")
            
    def _find_rail_at_position(self, position):
        """Encontra rail real na posição especificada"""
        x, y = position
        for element in self.trackplan_elements:
            if (element.get("type") == "rail" and 
                element.get("x") == x and 
                element.get("y") == y and
                not element.get("auto_rail")):  # Apenas rails reais
                return element
        return None
    
    def _hide_rail_visual(self, rail_element):
        """Oculta representação visual do rail preservando elemento"""
        try:
            if rail_element.get("canvas_ids"):
                for canvas_id in rail_element["canvas_ids"]:
                    if canvas_id:
                        self.trackplan_canvas.itemconfig(canvas_id, state='hidden')
            elif rail_element.get("canvas_id"):
                self.trackplan_canvas.itemconfig(rail_element["canvas_id"], state='hidden')
            
            # Marcar como oculto
            rail_element["_visual_hidden"] = True
            
            # Remover qualquer highlight azul residual
            if "original_image_key" in rail_element:
                try:
                    # Tentar restaurar imagem original se existir
                    if hasattr(self, 'element_images') and rail_element["original_image_key"] in self.element_images:
                        if rail_element.get("canvas_id"):
                            self.trackplan_canvas.itemconfig(
                                rail_element["canvas_id"],
                                image=self.element_images[rail_element["original_image_key"]]
                            )
                except Exception as e:
                    print(f"Erro ao restaurar imagem original do rail: {e}")
            
        except tk.TclError as e:
            print(f"Erro ao ocultar rail: {e}")
        except Exception as e:
            print(f"Erro inesperado ao ocultar rail: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_loading_error(self, error):
        """Manipula erros durante o carregamento"""
        error_msg = f"Erro ao carregar Trackplan: {str(error)}"
        messagebox.showerror("Erro", error_msg)
        
        import traceback
        traceback.print_exc()
    
    def create_xml_preview_tab(self):
        """Cria a aba de visualização XML com opção de multiview"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Visualização XML")
        
        # === BARRA DE CONTROLES ===
        controls_frame = ttk.Frame(frame)
        controls_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Botões de ação (lado esquerdo)
        action_buttons = ttk.Frame(controls_frame)
        action_buttons.pack(side=tk.LEFT)
        
        ttk.Button(action_buttons, text="Atualizar Preview", command=self.update_xml_preview).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_buttons, text="Salvar FdsConfig.xml", command=self.save_fds_config).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_buttons, text="Salvar Trackplan.xml", command=self.save_trackplan_xml).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_buttons, text="Gerar FdsRecovery.zip", command=self.generate_recovery_zip).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_buttons, text="Salvar Tudo", command=self.save_all_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_buttons, text="Validador", command=self.validate_xml).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(action_buttons, text="Gerar FADC", command=self.generate_fadc_aeb).pack(side=tk.LEFT, padx=(0, 5))

        # Controles de visualização (lado direito)
        view_controls = ttk.Frame(controls_frame)
        view_controls.pack(side=tk.RIGHT)
        
        # Dropdown
        ttk.Label(view_controls, text="Visualização:", font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        
        # Variável para controlar o tipo de visualização
        self.xml_view_mode = tk.StringVar(value="tabs")
        
        def defocus(event):
            event.widget.master.focus_set()
        
        # Combobox para modo de visualização
        view_options = [
            ("Abas", "tabs"),
            ("Lado a Lado", "side_by_side"), 
            ("Vertical", "vertical")
        ]
        
        view_combo = ttk.Combobox(view_controls, textvariable=self.xml_view_mode,
                                values=[option[0] for option in view_options],
                                width=10, state="readonly", font=('Arial', 9))
        view_combo.pack(side=tk.LEFT, padx=(0, 10))
        view_combo.bind("<FocusIn>", defocus)
        
        # Mapear valores visuais para valores internos
        self.view_mode_mapping = {option[0]: option[1] for option in view_options}
        self.reverse_view_mapping = {option[1]: option[0] for option in view_options}
        
        # Definir valor inicial
        view_combo.set("Abas")
        
        # Bind para mudança de seleção
        view_combo.bind("<<ComboboxSelected>>", self.on_view_mode_change)
        
        # Controles de fonte
        font_controls = ttk.Frame(view_controls)
        font_controls.pack(side=tk.RIGHT)
        
        ttk.Label(font_controls, text="Fonte:", font=('Arial', 8)).pack(side=tk.LEFT, padx=(0, 2))

        self.xml_font_size = tk.StringVar(value="10")
        font_combo = ttk.Combobox(font_controls, textvariable=self.xml_font_size, 
                                values=["8", "9", "10", "11", "12", "14", "16"], 
                                width=3, state="readonly")
        font_combo.pack(side=tk.LEFT, padx=(0, 5))
        font_combo.bind("<<ComboboxSelected>>", self.update_xml_font)
        font_combo.bind("<FocusIn>", defocus)
        
        ttk.Button(font_controls, text="🔍+", command=self.increase_xml_font, width=4).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(font_controls, text="🔍-", command=self.decrease_xml_font, width=4).pack(side=tk.LEFT)
        
        # === CONTAINER PRINCIPAL PARA MULTIVIEW ===
        self.xml_container = ttk.Frame(frame)
        self.xml_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Inicializar em modo abas
        self.create_xml_tabs_view()

    def create_config_tab(self):
        frame = ttk.Frame(self.notebook, style='Transparent.TFrame')
        self.notebook.add(frame, text="FADC")

        # PanedWindow horizontal: ESQUERDA | DIREITA
        main_paned_config = ttk.PanedWindow(frame, orient='horizontal')
        main_paned_config.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Pane esquerdo (tudo da lista e busca fica aqui)
        left_frame = ttk.Frame(main_paned_config)
        main_paned_config.add(left_frame, weight=3)

        # Pane direito
        right_frame = ttk.Frame(main_paned_config)
        main_paned_config.add(right_frame, weight=2)

        # === HEADER / AÇÕES (DENTRO do left_frame) ===
        header = ttk.Frame(left_frame, style='Transparent.TFrame', padding=(10, 8))
        header.pack(fill=tk.X)

        ttk.Label(
            header,
            text="Gerenciamento de IPs",
            font=('Segoe UI', 11, 'bold'),
            style='Corporate.TLabel'
        ).pack(side=tk.LEFT)

        self.main_ip_label_var = tk.StringVar(value="IP principal: (não definido)")
        ttk.Label(
            header,
            textvariable=self.main_ip_label_var,
            font=('Segoe UI', 9, 'bold'),
            style='Corporate.TLabel'
        ).pack(side=tk.LEFT, padx=(16, 0))

        actions = ttk.Frame(header, style='Transparent.TFrame')
        actions.pack(side=tk.RIGHT)

        ttk.Button(
            actions,
            text="Definir IP Principal",
            command=self.define_main_ip,
            style='Primary.TButton'
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            actions,
            text="Cadastrar IP",
            command=self.add_to_ip_list,
            style='Primary.TButton'
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            actions,
            text="Remover Selecionado",
            command=self.remove_selected_ip_entry,
            style='Primary.TButton'
        ).pack(side=tk.LEFT)

        # === BUSCA (DENTRO do left_frame) ===
        search_frame = ttk.LabelFrame(left_frame, text="Pesquisar", padding=10, style='Section.TLabelframe')
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 8))

        ttk.Label(
            search_frame,
            text="Pesquisar por IP ou Descrição:",
            font=('Segoe UI', 9, 'bold'),
            style='Corporate.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.ip_search_var = tk.StringVar()
        self.ip_search_var.trace_add('write', lambda *_: self.filter_ip_tree())

        self.ip_search_entry = ttk.Entry(
            search_frame,
            textvariable=self.ip_search_var,
            style='Corporate.TEntry',
            font=('Segoe UI', 9),
            width=40
        )
        self.ip_search_entry.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)

        ttk.Button(search_frame, text="Limpar", command=self.clear_ip_search).pack(side=tk.LEFT)

        # === LISTA (DENTRO do left_frame) ===
        table_frame = ttk.Frame(left_frame, style='Transparent.TFrame', padding=(10, 0, 10, 10))
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("IP (FDS)", "IP (FADC)", "Descricao", "Tem FDS?")
        self.ip_list = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)

        self.ip_list.heading("IP (FDS)", text="IP (FDS)")
        self.ip_list.heading("IP (FADC)", text="IP (FADC)")
        self.ip_list.heading("Descricao", text="Descrição")
        self.ip_list.heading("Tem FDS?", text="Tem FDS?")

        self.ip_list.column("IP (FDS)", width=160, anchor="center", stretch=False)
        self.ip_list.column("IP (FADC)", width=160, anchor="center", stretch=False)
        self.ip_list.column("Descricao", width=520, anchor="w", stretch=True)
        self.ip_list.column("Tem FDS?", width=100, anchor="center", stretch=False)
        ip_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.ip_list.yview)
        self.ip_list.configure(yscrollcommand=ip_scrollbar.set)

        self.ip_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ip_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        try:
            self.ip_list.tag_configure("main_ip", background="#fff2a8", foreground="#000000")
        except Exception:
            pass

        if not hasattr(self, "_ip_entries"):
            self._ip_entries = []
        
        if not hasattr(self, "abrigos_sem_fds"):
            self.abrigos_sem_fds = []

        if not hasattr(self, "main_ip"):
            self.main_ip = None
        
        if not hasattr(self, "abrigos_usados"):
            self.abrigos_usados = []

        # === DIREITA ===
        editor_title = ttk.Label(right_frame, text="Configuração FADC", font=('Arial', 12, 'bold'))
        editor_title.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        list_aeb = []

        self.combo_var = tk.StringVar(value="")
        self.cubicle_list = ttk.Combobox(right_frame, values = list_aeb, state='readonly', textvariable=self.combo_var)
        self.cubicle_list.grid(row=1, column=0, sticky="w", padx=5, pady=5)
    
        refresh_list_button = ttk.Button(right_frame, text="Atualizar Lista", command=lambda: self.refresh_cub_list())
        refresh_list_button.grid(row=1, column=0, sticky="e", padx=5, pady=5)

        self.aeb_com_tree = ttk.Treeview(right_frame, columns=("Nome", "Id", "Tipo"), show="headings", height=10)
        self.aeb_com_tree.heading("Nome", text="Nome")
        self.aeb_com_tree.heading("Id", text="Id")
        self.aeb_com_tree.heading("Tipo", text="Tipo")

        self.aeb_com_tree.column("Nome", width=120, anchor="center", stretch=False)
        self.aeb_com_tree.column("Id", width=80, anchor="center", stretch=False)
        self.aeb_com_tree.column("Tipo", width=100, anchor="center", stretch=False)
        self.aeb_com_tree.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        self.cubicle_list.bind("<<ComboboxSelected>>", self.on_cubicle_selected)    

        self.config_elem = ttk.Treeview(right_frame, columns=("Destino a rede", "Destino de Aeb", "Destino de diagnóstico"), show="headings", height=10)
        self.config_elem.heading("Destino a rede", text="Destino a rede")
        self.config_elem.heading("Destino de Aeb", text="Destino de Aeb")
        self.config_elem.heading("Destino de diagnóstico", text="Destino de diagnóstico")

        self.config_elem.column("Destino a rede", width=100, anchor="center", stretch=False)
        self.config_elem.column("Destino de Aeb", width=100, anchor="center", stretch=False)
        self.config_elem.column("Destino de diagnóstico", width=160, anchor="center", stretch=False)
        self.config_elem.grid(row=3, column=0, sticky="nsew", padx=5, pady=5)
        
        self.aeb_com_tree.bind("<<TreeviewSelect>>", self.on_config_elem_select)   
        self.refresh_cub_list()

        buttons = tk.Frame(right_frame)
        buttons.grid(row=4, column=0, sticky="ew", padx=5, pady=5)

        ttk.Button(
            buttons,
            text="Adicionar Destino de Aeb",
            command=self.add_destino_aeb,
            style='Corporate.TButton'
        ).pack(side=tk.LEFT)

        ttk.Button(
            buttons,
            text="Adicionar Destino de Diagnóstico",
            command=self.add_destino_diag,
            style='Corporate.TButton'
        ).pack(side=tk.LEFT)

    # === Cache de destinos (por elemento COM/AEB) ===
    def _dest_cache_init(self):
        if not hasattr(self, "_dest_cache_by_elem"):
            # elem_key -> {rede:set, aeb:set, diag:set, _locked:{rede,aeb,diag}}
            self._dest_cache_by_elem = {}

    def _dest_norm(self, value: str) -> str:
        s = str(value or "").strip()
        for suf in (" (FADC)", " (FDS)"):
            if s.endswith(suf):
                s = s[: -len(suf)].strip()
        return s

    def _dest_cache_get(self, elem_key: str) -> dict:
        self._dest_cache_init()
        if elem_key not in self._dest_cache_by_elem:
            self._dest_cache_by_elem[elem_key] = {
                "rede": set(),
                "aeb": set(),
                "diag": set(),
                "_locked": {"rede": False, "aeb": False, "diag": False},
            }
        return self._dest_cache_by_elem[elem_key]

    def _dest_cache_seed_from_tree(self, elem_key: str):
        """Se não houver cache para o elemento, semeia a partir do que está na tree atual."""
        self._dest_cache_init()
        if elem_key in self._dest_cache_by_elem:
            return
        cache = self._dest_cache_get(elem_key)
        try:
            for iid in self.config_elem.get_children():
                vals = self.config_elem.item(iid).get("values", [])
                if not vals:
                    continue
                v_rede = self._dest_norm(vals[0] if len(vals) > 0 else "")
                v_aeb = self._dest_norm(vals[1] if len(vals) > 1 else "")
                v_diag = self._dest_norm(vals[2] if len(vals) > 2 else "")
                if v_rede:
                    cache["rede"].add(v_rede)
                if v_aeb:
                    cache["aeb"].add(v_aeb)
                if v_diag:
                    cache["diag"].add(v_diag)
        except Exception:
            pass

    def _dest_cache_render_tree(self, elem_key: str):
        """Reescreve a config_elem a partir do cache (sem linhas em branco)."""
        cache = self._dest_cache_get(elem_key)

        rede_set = {self._dest_norm(x) for x in (cache.get("rede") or set()) if self._dest_norm(x)}
        aeb_set = {self._dest_norm(x) for x in (cache.get("aeb") or set()) if self._dest_norm(x)}
        diag_set = {self._dest_norm(x) for x in (cache.get("diag") or set()) if self._dest_norm(x)}

        all_names = sorted(rede_set | aeb_set | diag_set, key=lambda s: s.lower())

        self.config_elem.delete(*self.config_elem.get_children())
        for name in all_names:
            v1 = f"{name} (FADC)" if name in rede_set else ""
            v2 = name if name in aeb_set else ""
            v3 = name if name in diag_set else ""
            self.config_elem.insert("", "end", values=(v1, v2, v3))

    def add_destino_aeb(self):
        sel = self.aeb_com_tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um AEB/COM na lista primeiro.")
            return
        
        # Identidade do item selecionado (para persistir por dispositivo)
        item_data = self.aeb_com_tree.item(sel[0])
        values = item_data.get("values", [])
        if not values or len(values) < 3:
            messagebox.showwarning("Aviso", "Item selecionado inválido.")
            return

        device_name = str(values[0])
        device_id = str(values[1])
        device_type = str(values[2])
        device_key = f"{device_type}:{device_id}"

        # Semeia cache (se necessário) a partir do que está na tree
        self._dest_cache_seed_from_tree(device_key)
        cache = self._dest_cache_get(device_key)

        # Conjunto atual editável no popup: vamos editar explicitamente o destino de AEB
        # (e na confirmação espelhar para Rede também, com lock)
        current_set = set(cache.get("aeb") or set())

        # Manter compatibilidade com self.add_list
        self.add_list = sorted(current_set, key=lambda s: str(s).lower())

        # Montar lista de cubículos disponíveis (por nome)
        all_cub_names = []
        for cubicle in getattr(self, "cubicles_data", []) or []:
            name = (cubicle or {}).get("name", "")
            name = str(name).strip()
            if name and name != self.combo_var.get():
                all_cub_names.append(name)

        # UI
        ip_screen = tk.Toplevel(self.root)
        ip_screen.title("Adição de Destino de Aeb")
        window_width = 720
        window_height = 520

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)
        ip_screen.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

        tk.Label(
            ip_screen,
            text=f"Destino de AEB - {device_name}",
            font=('Arial', 12, 'bold')
        ).pack(fill=tk.X, pady=10, padx=10)

        mid = ttk.Frame(ip_screen, padding=10)
        mid.pack(fill=tk.BOTH, expand=True)

        left = ttk.LabelFrame(mid, text="Abrigos Disponíveis", padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        center = ttk.Frame(mid)
        center.pack(side=tk.LEFT, fill=tk.Y, padx=10)

        right = ttk.LabelFrame(mid, text="Abrigos já pertencentes", padding=10)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        available_abr = tk.Listbox(left, height=18, selectmode=tk.EXTENDED)
        available_abr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        avail_scroll = ttk.Scrollbar(left, orient="vertical", command=available_abr.yview)
        avail_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        available_abr.configure(yscrollcommand=avail_scroll.set)

        used_abr = tk.Listbox(right, height=18, selectmode=tk.EXTENDED)
        used_abr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        assigned_scroll = ttk.Scrollbar(right, orient="vertical", command=used_abr.yview)
        assigned_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        used_abr.configure(yscrollcommand=assigned_scroll.set)

        def refresh_lists():
            """Reconstrói as duas listas a partir do conjunto current_set."""
            # Direita: já selecionados (ordenado p/ ficar estável)
            used_sorted = sorted(current_set, key=lambda s: str(s).lower())

            # Esquerda: disponíveis = todos - usados (ordenado)
            avail_sorted = sorted(set(all_cub_names) - set(used_sorted), key=lambda s: str(s).lower())

            available_abr.delete(0, tk.END)
            for name in avail_sorted:
                available_abr.insert(tk.END, name)

            used_abr.delete(0, tk.END)
            for name in used_sorted:
                used_abr.insert(tk.END, name)

        def on_add():
            """Move seleção da esquerda -> direita, sem duplicar."""
            sel_idx = list(available_abr.curselection())
            if not sel_idx:
                return

            # Captura por texto (mais seguro que depender de índices após refresh)
            picked = [available_abr.get(i) for i in sel_idx]
            for name in picked:
                n = str(name).strip()
                if n:
                    current_set.add(n)

            refresh_lists()

        def on_remove():
            """Remove seleção da direita."""
            sel_idx = list(used_abr.curselection())
            if not sel_idx:
                return

            picked = [used_abr.get(i) for i in sel_idx]
            for name in picked:
                n = str(name).strip()
                if n in current_set:
                    current_set.remove(n)

            refresh_lists()

        ttk.Button(center, text="Adicionar →", command=on_add).pack(fill=tk.X, pady=(0, 8))
        ttk.Button(center, text="← Remover", command=on_remove).pack(fill=tk.X, pady=(0, 20))

        # Rodapé com Confirmar/Cancelar para persistir
        bottom = ttk.Frame(ip_screen, padding=10)
        bottom.pack(fill=tk.X)

        def on_confirm():
            """Persiste os abrigos escolhidos no cache do elemento e reescreve a tree a partir do cache."""
            try:
                # 1) Ler a lista final (direita) => é a "fonte da verdade"
                chosen = []
                for i in range(used_abr.size()):
                    name = (used_abr.get(i) or "").strip()
                    if name:
                        chosen.append(name)

                chosen_set = set(chosen)

                # 2) Persistir no cache do elemento
                cache_local = self._dest_cache_get(device_key)
                cache_local["aeb"] = set(chosen_set)

                # Espelhar também para Rede (conforme regra) e travar ambas contra sobrescrita automática
                cache_local["rede"] = set(chosen_set)
                cache_local["_locked"]["aeb"] = True
                cache_local["_locked"]["rede"] = True

                self.add_list = sorted(chosen_set, key=lambda s: s.lower())

                # 3) Reescrever a tree a partir do cache
                if hasattr(self, "config_elem") and self.config_elem:
                    self._dest_cache_render_tree(device_key)

                # 4) Fechar janela
                try:
                    ip_screen.destroy()
                except Exception:
                    pass

            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao confirmar destinos de AEB: {e}")

        def on_cancel():
            ip_screen.destroy()

        ttk.Button(bottom, text="Confirmar", command=on_confirm).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(bottom, text="Cancelar", command=on_cancel).pack(side=tk.RIGHT)

        refresh_lists()

    def add_destino_diag(self):
        sel = self.aeb_com_tree.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um AEB/COM na lista primeiro.")
            return

        item_data = self.aeb_com_tree.item(sel[0])
        values = item_data.get("values", [])
        if not values or len(values) < 3:
            messagebox.showwarning("Aviso", "Item selecionado inválido.")
            return

        device_name = str(values[0])
        device_id = str(values[1])
        device_type = str(values[2])
        device_key = f"{device_type}:{device_id}"

        # Semeia cache (se necessário) a partir do que está na tree
        self._dest_cache_seed_from_tree(device_key)
        cache = self._dest_cache_get(device_key)

        current_set = set(cache.get("diag") or set())

        # Montar lista de cubículos disponíveis
        all_cub_names = []
        for cubicle in getattr(self, "cubicles_data", []) or []:
            name = (cubicle or {}).get("name", "")
            name = str(name).strip()
            if name and name != self.combo_var.get():
                all_cub_names.append(name)
        all_cub_names = sorted(set(all_cub_names), key=lambda s: s.lower())

        ip_screen = tk.Toplevel(self.root)
        ip_screen.title("Adição de Destino de Diagnóstico")
        window_width = 720
        window_height = 520

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)
        ip_screen.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

        tk.Label(
            ip_screen,
            text=f"Destino de Diagnóstico - {device_name}",
            font=('Arial', 12, 'bold')
        ).pack(fill=tk.X, pady=10, padx=10)

        mid = ttk.Frame(ip_screen, padding=10)
        mid.pack(fill=tk.BOTH, expand=True)

        left = ttk.LabelFrame(mid, text="Abrigos Disponíveis", padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        center = ttk.Frame(mid)
        center.pack(side=tk.LEFT, fill=tk.Y, padx=10)

        right = ttk.LabelFrame(mid, text="Abrigos já pertencentes", padding=10)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        available_abr = tk.Listbox(left, height=18, selectmode=tk.EXTENDED)
        available_abr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        avail_scroll = ttk.Scrollbar(left, orient="vertical", command=available_abr.yview)
        avail_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        available_abr.configure(yscrollcommand=avail_scroll.set)

        used_abr = tk.Listbox(right, height=18, selectmode=tk.EXTENDED)
        used_abr.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        assigned_scroll = ttk.Scrollbar(right, orient="vertical", command=used_abr.yview)
        assigned_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        used_abr.configure(yscrollcommand=assigned_scroll.set)

        def refresh_lists():
            used_sorted = sorted(current_set, key=lambda s: str(s).lower())
            avail_sorted = sorted(set(all_cub_names) - set(used_sorted), key=lambda s: str(s).lower())

            available_abr.delete(0, tk.END)
            for name in avail_sorted:
                available_abr.insert(tk.END, name)

            used_abr.delete(0, tk.END)
            for name in used_sorted:
                used_abr.insert(tk.END, name)

        def on_add():
            sel_idx = list(available_abr.curselection())
            if not sel_idx:
                return
            picked = [available_abr.get(i) for i in sel_idx]
            for name in picked:
                n = str(name).strip()
                if n:
                    current_set.add(n)
            refresh_lists()

        def on_remove():
            sel_idx = list(used_abr.curselection())
            if not sel_idx:
                return
            picked = [used_abr.get(i) for i in sel_idx]
            for name in picked:
                n = str(name).strip()
                if n in current_set:
                    current_set.remove(n)
            refresh_lists()

        ttk.Button(center, text="Adicionar →", command=on_add).pack(fill=tk.X, pady=(0, 8))
        ttk.Button(center, text="← Remover", command=on_remove).pack(fill=tk.X, pady=(0, 20))

        bottom = ttk.Frame(ip_screen, padding=10)
        bottom.pack(fill=tk.X)

        def on_confirm():
            try:
                chosen = []
                for i in range(used_abr.size()):
                    name = (used_abr.get(i) or "").strip()
                    if name:
                        chosen.append(name)

                chosen_set = set(chosen)
                cache_local = self._dest_cache_get(device_key)
                cache_local["diag"] = set(chosen_set)
                cache_local["_locked"]["diag"] = True

                if hasattr(self, "config_elem") and self.config_elem:
                    self._dest_cache_render_tree(device_key)

                ip_screen.destroy()
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao confirmar destinos de diagnóstico: {e}")

        def on_cancel():
            ip_screen.destroy()

        ttk.Button(bottom, text="Confirmar", command=on_confirm).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(bottom, text="Cancelar", command=on_cancel).pack(side=tk.RIGHT)

        refresh_lists()

    def define_main_ip(self):
        sel = self.ip_list.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um IP para definir como principal.")
            return

        if len(sel) > 1:
            messagebox.showwarning("Aviso", "Seleção múltipla não suportada para esta ação.")
            return

        iid = sel[0]
        item = self.ip_list.item(iid)
        values = item.get("values", [])

        if not values or len(values) < 1:
            messagebox.showwarning("Aviso", "Item selecionado inválido.")
            return

        # Regra: usar IP (FDS) como chave do main_ip
        self.main_ip = values[0]

        # Aplicar marcação visual
        self._apply_main_ip_marker()

    def on_config_elem_select(self, event):
        sel = self.aeb_com_tree.selection()
        if not sel:
            return
        
        if len(sel) > 1:
            messagebox.showwarning("Aviso", "Seleção múltipla não suportada para esta ação.")
            return
        
        item_data = self.aeb_com_tree.item(sel[0])
        values = item_data.get("values", [])

        if len(values) < 3:
            return

        device_id = str(values[1])
        device_type = str(values[2])
        device_key = f"{device_type}:{device_id}"

        # Semeia cache se ainda não existir
        self._dest_cache_seed_from_tree(device_key)
        cache = self._dest_cache_get(device_key)

        # Se não for COM, apenas renderiza o cache existente (permite cache também para AEB)
        if device_type != 'Com':
            self._dest_cache_render_tree(device_key)
            return
        
        cubicle_names = set()  # Destino a rede (auto)
        aeb_send = set()       # Destino de Aeb (auto - se aplicável)
        fds_send = set()       # Destino de diagnóstico (auto)

        selected_cubicle_name = (self.combo_var.get() or "").strip()
        if not selected_cubicle_name:
            return
                
        # Adiciona o próprio cubículo selecionado como destino, se aplicável
        if self.combo_var.get() not in self.abrigos_sem_fds:
            fds_send.add(self.combo_var.get())
            cubicle_names.add(self.combo_var.get())

        # Adiciona o FDS do abrigo principal para todos os outros
        for child_id in self.ip_list.get_children():
            item_values = self.ip_list.item(child_id)['values']
            if self.main_ip == item_values[0] and item_values[2] not in self.abrigos_sem_fds:
                fds_send.add(item_values[2])
                cubicle_names.add(item_values[2])

        def _suffix(value) -> str:
            s = str(value or "").strip()
            return s[1:] if len(s) > 1 else ""

        def _is_fma_id(value) -> bool:
            s = str(value or "").strip()
            return len(s) > 1 and s[0] in ('3', '4') and s[1:].isdigit()

        def _is_sensor_id(value) -> bool:
            s = str(value or "").strip()
            return len(s) > 1 and s[0] == '2' and s[1:].isdigit()

        def _cubicle_suffixes(cubicle: dict) -> set:
            out = set()
            for _, slot in self._iter_cubicle_slots(cubicle):
                if not slot or slot.get('type') in ('EmptySlot', 'Psc', None, ''):
                    continue
                stype = slot.get('type')
                if stype in ('Aeb', 'IoExb'):
                    sid = slot.get('id')
                    if sid:
                        out.add(_suffix(sid))
            return out

        def _selected_sensor_suffixes(cubicle: dict) -> set:
            # Para o teste, sensores e AEBs são tratados como equivalentes pelo sufixo.
            return _cubicle_suffixes(cubicle)

        selected_cubicle = None
        for cub in self.cubicles_data:
            if (cub.get('name', '') or '').strip() == selected_cubicle_name:
                selected_cubicle = cub
                break
        if not selected_cubicle:
            self.config_elem.delete(*self.config_elem.get_children())
            return

        selected_suffixes = _selected_sensor_suffixes(selected_cubicle)

        all_fmas = [
            f for f in getattr(self, 'trackplan_elements', [])
            if isinstance(f, dict) and f.get('type') == 'fma' and _is_fma_id(f.get('id'))
        ]

        # Para cada outro cubículo, checar se alguma FMA "dele" referencia sensor do cubículo selecionado.
        for cubicle in self.cubicles_data:
            name = (cubicle.get('name', 'Desconhecido') or '').strip()
            if not name or name == selected_cubicle_name:
                continue

            cub_suffixes = _cubicle_suffixes(cubicle)
            if not cub_suffixes:
                continue

            depends = False
            for fma in all_fmas:
                # FMA pertence ao cubículo se seu sufixo casa com algum AEB/IoExb do cubículo
                if _suffix(fma.get('id')) not in cub_suffixes:
                    continue

                for sensor_data in fma.get('associated_sensors', []) or []:
                    if not isinstance(sensor_data, dict):
                        continue
                    ref_id = sensor_data.get('refId') or sensor_data.get('id')
                    if not _is_sensor_id(ref_id):
                        continue

                    if _suffix(ref_id) in selected_suffixes:
                        depends = True
                        break
                if depends:
                    break

            if depends:
                cubicle_names.add(name)

        # === Atualizar cache com dados automáticos (respeitando locks) e renderizar ===
        auto_rede = {self._dest_norm(x) for x in cubicle_names if self._dest_norm(x)}
        auto_aeb = {self._dest_norm(x) for x in aeb_send if self._dest_norm(x)}
        auto_diag = {self._dest_norm(x) for x in fds_send if self._dest_norm(x)}

        if not cache.get("_locked", {}).get("rede", False):
            cache["rede"] = set(auto_rede)
        if not cache.get("_locked", {}).get("aeb", False) and auto_aeb:
            cache["aeb"] = set(auto_aeb)
        if not cache.get("_locked", {}).get("diag", False):
            cache["diag"] = set(auto_diag)

        self._dest_cache_render_tree(device_key)

    def on_cubicle_selected(self, event):
        sel = event.widget.get()
        for cubicle in self.cubicles_data:
            name = cubicle.get('name', 'Desconhecido')
            if name == self.combo_var.get():
                self.insere_dados_com_aeb_list(cubicle)
        
        self.refresh_cub_list()

    def insere_dados_com_aeb_list(self, cubicle):
        """Insere os dados dos AEBs na TreeView."""
        self.aeb_com_tree.delete(*self.aeb_com_tree.get_children())
        for _, slot in self._iter_cubicle_slots(cubicle):
            if not slot or slot.get('type') in ('EmptySlot', 'Psc', None, ''):
                continue
            stype = slot.get('type')
            if stype in ['Com', 'Aeb']:
                self.aeb_com_tree.insert("", "end", values=(slot.get('name', 'Desconhecido'),
                                                            slot.get('id', 'N/A'),
                                                            stype))
                                                            
    def refresh_cub_list(self):
        """Atualiza a lista de cubículos no combobox da aba FADC (self.cubicle_list)
        e também no combobox do popup de IP (self.abrigo_list), se existir.
        """
        cubs = getattr(self, "cubicles_data", []) or []

        # Coletar nomes válidos
        names = []
        for cubicle in cubs:
            n = (cubicle.get("name", "") or "").strip()
            if n:
                names.append(n)

        # Únicos + ordenados (ordenar ajuda o usuário)
        list_cub = sorted(set(names), key=lambda s: s.lower())

        # 1) Combobox da aba FADC (direita)
        try:
            if hasattr(self, "cubicle_list") and self.cubicle_list:
                self.cubicle_list.configure(values=list_cub)

                # Se o selecionado não existe mais, limpar
                cur = (self.combo_var.get() or "").strip() if hasattr(self, "combo_var") else ""
                if cur and cur in list_cub:
                    pass
                else:
                    self.combo_var.set(list_cub[0] if not cur and list_cub else cur)
        except Exception as e:
            print(f"refresh_cub_list: falha ao atualizar cubicle_list: {e}")

        used_desc = set()
        try:
            for _ip_fds, _ip_fadc, desc, _tem_fds in (getattr(self, "_ip_entries", []) or []):
                d = (str(desc) or "").strip()
                if d:
                    used_desc.add(d)
        except Exception:
            used_desc = set()

        list_cub = [abrigo for abrigo in list_cub if abrigo not in used_desc]

        # 2) Combobox do popup "Cadastrar IP" (Descrição)
        try:
            if hasattr(self, "abrigo_list") and self.abrigo_list and self.abrigo_list.winfo_exists():
                self.abrigo_list.configure(values=list_cub)

                # Preservar seleção atual se possível; senão, selecionar o primeiro item
                if hasattr(self, "combo_var_ip") and self.combo_var_ip:
                    cur_ip = (self.combo_var_ip.get() or "").strip()
                    if cur_ip in list_cub:
                        # ok, mantém
                        pass
                    else:
                        self.combo_var_ip.set(list_cub[0] if not cur_ip and list_cub else cur_ip)
        except Exception as e:
            print(f"refresh_cub_list: falha ao atualizar abrigo_list: {e}")

    def _apply_main_ip_marker(self):
        """Aplica/atualiza a marcação visual do IP principal na Treeview."""
        try:
            # Atualizar label
            if getattr(self, "main_ip", None):
                if hasattr(self, "main_ip_label_var"):
                    self.main_ip_label_var.set(f"IP principal: {self.main_ip}")
            else:
                if hasattr(self, "main_ip_label_var"):
                    self.main_ip_label_var.set("IP principal: (não definido)")

            # Limpar tags antigas e reaplicar
            for iid in self.ip_list.get_children():
                self.ip_list.item(iid, tags=())

            if not getattr(self, "main_ip", None):
                return

            for iid in self.ip_list.get_children():
                values = self.ip_list.item(iid).get("values", [])
                if values and values[0] == self.main_ip:
                    self.ip_list.item(iid, tags=("main_ip",))
        except Exception as e:
            print(f"_apply_main_ip_marker: {e}")

    def filter_ip_tree(self):
        """Filtra a TreeView de IPs por IP/Descrição."""
        term = (self.ip_search_var.get() or "").strip().lower()

        # Limpar tree
        self.ip_list.delete(*self.ip_list.get_children())

        # Repopular
        for ip_fds, ip_fadc, desc, tem_fds in getattr(self, "_ip_entries", []):
            if not term or term in ip_fds.lower() or term in ip_fadc.lower() or term in desc.lower():
                self.ip_list.insert("", "end", values=(ip_fds, ip_fadc, desc, tem_fds))
        
        self._apply_main_ip_marker()

    def clear_ip_search(self):
        """Limpa a busca da aba FADC."""
        if hasattr(self, "ip_search_var"):
            self.ip_search_var.set("")
        
        self._apply_main_ip_marker()

    def remove_selected_ip_entry(self):
        """Remove item selecionado da lista e do cache."""
        sel = self.ip_list.selection()
        if not sel:
            messagebox.showwarning("Aviso", "Selecione um item para remover.")
            return

        if not hasattr(self, "_ip_entries"):
            self._ip_entries = []

        def _norm(s) -> str:
            return (str(s) if s is not None else "").strip()

        removed_any = False

        # Remover do cache comparando campos estáveis (não depender do bool/string do "Tem FDS?")
        for iid in sel:
            values = self.ip_list.item(iid, "values") or []
            if len(values) < 3:
                continue

            ip_fds = _norm(values[0])
            ip_fadc = _norm(values[1])
            desc = _norm(values[2])

            new_entries = []
            removed_here = False
            for e in self._ip_entries:
                try:
                    e_ip_fds, e_ip_fadc, e_desc, e_tem_fds = e
                except Exception:
                    new_entries.append(e)
                    continue

                if _norm(e_ip_fds) == ip_fds and _norm(e_ip_fadc) == ip_fadc and _norm(e_desc) == desc:
                    removed_here = True
                    continue

                new_entries.append(e)

            if removed_here:
                self._ip_entries = new_entries
                removed_any = True

        if not removed_any:
            messagebox.showwarning("Aviso", "Não foi possível remover (item não encontrado no cache).")
            return

        # Se removeu o IP principal, limpar main_ip
        try:
            if getattr(self, "main_ip", None):
                still_exists = any(_norm(e[0]) == _norm(self.main_ip) for e in self._ip_entries if isinstance(e, (list, tuple)) and len(e) >= 1)
                if not still_exists:
                    self.main_ip = None
        except Exception:
            pass

        # Recalcular listas derivadas (evita estado inconsistente)
        try:
            self.abrigos_usados = [_norm(desc) for (_ip_fds, _ip_fadc, desc, _tem_fds) in self._ip_entries if _norm(desc)]
        except Exception:
            self.abrigos_usados = []

        try:
            self.abrigos_sem_fds = [
                _norm(desc)
                for (_ip_fds, _ip_fadc, desc, tem_fds) in self._ip_entries
                if _norm(desc) and not bool(tem_fds)
            ]
        except Exception:
            self.abrigos_sem_fds = []

        # Atualizar UI
        self.filter_ip_tree()
        self.refresh_cub_list()

    def save_ip_entry(self, ip_fds, ip_fadc, description, tem_fds, window):
        """Salva o Ip e descrição na lista de IPs"""
        ip_fds = (ip_fds or "").strip()
        ip_fadc = (ip_fadc or "").strip()
        description = (description or "").strip()
        
        if not hasattr(self, "abrigos_usados"):
            self.abrigos_usados = []

        if not ip_fds or not ip_fadc or not description:
            messagebox.showwarning("Aviso", "Preencha IP e Descrição.")
            return

        if " " in ip_fds or " " in ip_fadc:
            messagebox.showwarning("Aviso", "O IP não pode conter espaços.")
            return

        if not hasattr(self, "_ip_entries"):
            self._ip_entries = []

        if (not self._is_valid_ipv4(ip_fds)) or (not self._is_valid_ipv4(ip_fadc)):
            messagebox.showwarning("Aviso", "Formato de IP inválido. Use a.b.c.d (0..255).")
            return

        if ip_fadc == ip_fds:
            messagebox.showwarning("Aviso", "IP (FDS) e IP (FADC) não podem ser iguais.")
            return

        item = (ip_fds, ip_fadc, description, tem_fds)

        for items in self.ip_list.get_children():
            item_values = self.ip_list.item(items, "values")     
            if (ip_fds == item_values[0] or ip_fadc == item_values[1]) and description == item_values[2]:
                messagebox.showinfo("Aviso", "IP já está cadastrado com a mesma descrição.")
                return
            elif (ip_fds == item_values[0] or ip_fadc == item_values[1]) and description != item_values[2]:
                messagebox.showinfo("Aviso", "IP já está cadastrado com descrição diferente.")
                return
            elif (ip_fds != item_values[0] or ip_fadc != item_values[1]) and description == item_values[2]:
                messagebox.showinfo("Aviso", "Esta descrição já está cadastrada com outro IP.")
                return
        
        if not hasattr(self, "abrigos_sem_fds"):
            self.abrigos_sem_fds = []

        if not tem_fds:
            self.abrigos_sem_fds.append(description)
        
        self.abrigos_usados.append(description)
        self._ip_entries.append(item)
        self.filter_ip_tree()

        try:
            window.destroy()
        except Exception:
            pass

    def add_to_ip_list(self):
        """ Adiciona Ip a lista de IPs"""
        ip_screen = tk.Toplevel(self.root)
        ip_screen.title("Configuração de IPs")
        window_width = 340
        window_height = 320
        list_abrigos = []

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = int(screen_width/2 - window_width/2)
        center_y = int(screen_height/2 - window_height/2)

        ip_screen.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        
        tk.Label(ip_screen, text="Configuração de IPs", font=('Arial', 12, 'bold')).grid(row=0, column=0, pady=10, padx=10)

        texts_frame = ttk.Frame(ip_screen, padding=10)
        texts_frame.grid(row=1, column=0, padx=10, pady=10)

        tk.Label(texts_frame, text="IP FDS:").grid(row=1, column=0, sticky=tk.W, pady=5)
        
        ip_fds_entry = tk.Entry(texts_frame)
        ip_fds_entry.grid(row=1, column=1, pady=5)

        tk.Label(texts_frame, text="IP FADC:").grid(row=2, column=0, sticky=tk.W, pady=5)
        
        ip_fadc_entry = tk.Entry(texts_frame)
        ip_fadc_entry.grid(row=2, column=1, pady=5)

        tk.Label(texts_frame, text="Descrição:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.combo_var_ip = tk.StringVar(value="")
        self.abrigo_list = ttk.Combobox(texts_frame, values = list_abrigos, state='readonly', textvariable=self.combo_var_ip)
        self.abrigo_list.grid(row=3, column=1, sticky="e", padx=5, pady=5)

        def on_main_ip_change():
            if main_ip_var.get() == 1 and ip_fds_entry.get():
                self.main_ip = ip_fds_entry.get()

        main_ip_var =tk.IntVar()
        tem_fds_var = tk.BooleanVar(value=1)

        ttk.Checkbutton(texts_frame,
            text="Definir como IP principal",
            variable=main_ip_var,
            command=on_main_ip_change,
            onvalue=1,
            offvalue=0
        ).grid(row=4, column=0, pady=5, sticky='w')

        ttk.Checkbutton(texts_frame,
            text="Possui FDS?",
            variable=tem_fds_var,
        ).grid(row=5, column=0, pady=5, sticky='w')

        buttons_frame = ttk.Frame(ip_screen, padding=10)
        buttons_frame.grid(row=6, column=0)
        confirm_button = ttk.Button(buttons_frame, text="Confirmar", 
                                    command=lambda: self.save_ip_entry(ip_fds_entry.get(), ip_fadc_entry.get(), self.combo_var_ip.get(), tem_fds_var.get(), ip_screen))
        confirm_button.grid(row=0, column=0, padx=5)

        cancel_button = ttk.Button(buttons_frame, text="Cancelar", command=ip_screen.destroy)
        cancel_button.grid(row=0, column=1, padx=5)

        self.refresh_cub_list()

    def on_view_mode_change(self, event=None):
        """Callback para mudança no dropdown de visualização"""
        try:
            # Obter valor selecionado no combobox
            selected_display = self.xml_view_mode.get()
            
            # Mapear para valor interno
            if selected_display in self.view_mode_mapping:
                internal_value = self.view_mode_mapping[selected_display]
                
                # Salvar o valor interno na variável
                self.xml_view_mode.set(internal_value)
                
                # Executar mudança de visualização
                self.switch_xml_view_mode()
                
                # Restaurar valor de display no combobox
                event.widget.set(selected_display)
            else:
                print(f"Valor de visualização não reconhecido: {selected_display}")
                
        except Exception as e:
            print(f"Erro ao processar mudança de visualização: {e}")

    def initialize_generator(self):
        """Inicializa o gerador com valores padrão"""
        try:
            # Obter valores dos campos com fallbacks seguros
            if self.fds_model == "FDS102":  
                network = NetworkConfig(
                    ip_net1=self.form_fields.get("IpAddressNet1", tk.StringVar()).get() or "192.168.1.12",
                    mask_net1=self.form_fields.get("MaskNet1", tk.StringVar()).get() or "255.255.255.0",
                    ip_net2=self.form_fields.get("IpAddressNet2", tk.StringVar()).get() or "192.168.0.12",
                    mask_net2=self.form_fields.get("MaskNet2", tk.StringVar()).get() or "255.255.255.0",
                    default_gateway=self.form_fields.get("DefaultGateway", tk.StringVar()).get() or "Gateway2",
                    gateway_net1=self.form_fields.get("GatewayAddressNet1", tk.StringVar()).get() or "192.168.1.1",
                    gateway_net2=self.form_fields.get("GatewayAddressNet2", tk.StringVar()).get() or "192.168.0.1",
                    udp_port=self._safe_int_get("UdpPortFadc", 45),
                    time_server1=self.form_fields.get("TimeServer1", tk.StringVar()).get() or "",
                    time_server2=self.form_fields.get("TimeServer2", tk.StringVar()).get() or ""
                )

                station = StationConfig(
                    config_version=self.form_fields.get("ConfigVersion", tk.StringVar()).get() or "1.0",
                    station_name=self.form_fields.get("StationName", tk.StringVar()).get() or "AREAIS",
                    fds_name=self.form_fields.get("FdsName", tk.StringVar()).get() or "ABRIGO 20 (IAA-4)",
                    timezone=self.form_fields.get("Timezone", tk.StringVar()).get() or "America/Sao_Paulo"
                )
            else:
                network = NetworkConfig(
                ip_net1=self.form_fields.get("IpAddressNet1", tk.StringVar()).get() or "192.168.1.12",
                mask_net1=self.form_fields.get("MaskNet1", tk.StringVar()).get() or "255.255.255.0",
                ip_net2=self.form_fields.get("IpAddressNet2", tk.StringVar()).get() or "192.168.0.12",
                mask_net2=self.form_fields.get("MaskNet2", tk.StringVar()).get() or "255.255.255.0",
                gateway_net1=self.form_fields.get("GatewayAddressNet1", tk.StringVar()).get() or "192.168.1.1",
                gateway_net2=self.form_fields.get("GatewayAddressNet2", tk.StringVar()).get() or "192.168.0.1",
                udp_port=self._safe_int_get("UdpPortFadc", 45),
                time_server1=self.form_fields.get("TimeServer1", tk.StringVar()).get() or "",
                time_server2=self.form_fields.get("TimeServer2", tk.StringVar()).get() or ""
                )

                station = StationConfig(
                    config_version=self.form_fields.get("ConfigVersion", tk.StringVar()).get() or "1.0",
                    station_name=self.form_fields.get("StationName", tk.StringVar()).get() or "AREAIS",
                    fds_name=self.form_fields.get("FdsName", tk.StringVar()).get() or "ABRIGO 20 (IAA-4)",
                    timezone=self.form_fields.get("Timezone", tk.StringVar()).get() or "CET-1CEST-2,M3.5.0/02:00:00,M10.5.0/03:00:00"
                )
            
            self.current_generator = FDSConfigGenerator(network, station)
            
            # Atualizar interface se disponível
            if hasattr(self, 'update_elements_tree'):
                self.update_elements_tree()
                            
        except Exception as e:
            print(f"Erro ao inicializar gerador: {e}")
            # Fallback para inicialização básica
            try:
                self.current_generator = None
                print("Gerador não inicializado - funcionalidade limitada")
            except:
                pass
    
    def _safe_int_get(self, field_name, default_value):
        """Obtém valor inteiro de um campo com fallback seguro"""
        try:
            field_value = self.form_fields.get(field_name, tk.StringVar()).get()
            return int(field_value) if field_value else default_value
        except (ValueError, TypeError):
            return default_value
    
    def update_elements_tree(self):
        """Atualiza a árvore de elementos"""
        self.elements_tree.delete(*self.elements_tree.get_children())

        if self.current_generator:
            search_text = self.search_var.get().strip().lower() if hasattr(self, 'search_var') else ""

            # Ordenar elementos por ID crescente
            sorted_elements = sorted(
                self.current_generator.elements,
                key=lambda e: getattr(e, 'element_id', 0)
            )

            def matches_search(e):
                if not search_text:
                    return True
                # Coletar campos com segurança
                elem_id = str(getattr(e, 'element_id', '')).lower()
                elem_type = str(getattr(e, 'element_type', '')).lower()
                elem_assignment = str(getattr(e, 'element_assignment', '')).lower()

                # Buscar em ID, Tipo e Atribuição
                return (
                    search_text in elem_id or
                    search_text in elem_type or
                    search_text in elem_assignment
                )

            for element in sorted_elements:
                if not matches_search(element):
                    continue

                # Montar valores seguros
                eid = getattr(element, 'element_id', '')
                etype = getattr(element, 'element_type', '')
                assign = getattr(element, 'element_assignment', '')
                # TrackplanID pode não existir; use vazio
                trackplan_id = getattr(element, 'element_trackplan_id', '')

                self.elements_tree.insert(
                    "", "end",
                    values=(eid, etype, assign, trackplan_id)
                )
    
    def filter_elements_tree(self, *args):
        """Filtra a árvore de elementos baseado na pesquisa"""
        self.update_elements_tree()
    
    def clear_search(self):
        """Limpa o campo de pesquisa"""
        if hasattr(self, 'search_var'):
            self.search_var.set("")

    def verifica_unico(self, element_id, element_type):
        """Verifica se já existe um elemento do tipo especificado"""
        for element in self.current_generator.elements:
            if element.element_id == element_id and element.element_type == element_type:
                return False
        return True

    def add_com_master(self):
        """Adiciona um ComMaster"""
        element_id = simpledialog.askinteger("ComMaster", "Digite o Element ID:")
        if element_id < 0:
            messagebox.showerror("Erro", "Valores negativos não são aceitos")
            return
        if not self.verifica_unico(element_id, 'ComMaster'):
            messagebox.showwarning("Aviso", "Já existe um ComMaster com este ID.")
            return
        if element_id:
            self.current_generator.add_com_master(element_id)
            self.update_elements_tree()
            self._mark_content_changed()
    
    def add_aeb(self):
        """Adiciona um AEB com ID normalizado para 4 dígitos"""
        element_id = simpledialog.askinteger("AEB", "Digite o Element ID:")
        if element_id < 0:
            messagebox.showerror("Erro", "Valores negativos não são aceitos")
            return
        if not self.verifica_unico(element_id, 'Aeb'):
            messagebox.showwarning("Aviso", "Já existe uma AEB com este ID.")
            return
        if element_id:
            self.current_generator.add_aeb_with_counting_head(element_id)
            self.update_elements_tree()
            self._mark_content_changed()
    
    def add_counting_head(self):
        """Adiciona um CountingHead com atribuição automática ZP{element_id}"""
        element_id = simpledialog.askinteger("CountingHead", "Digite o Element ID:")
        if element_id < 0:
            messagebox.showerror("Erro", "Valores negativos não são aceitos")
            return
        if not self.verifica_unico(element_id, 'CountingHead'):
            messagebox.showwarning("Aviso", "Já existe um CountingHead com este ID.")
            return
        if element_id:
            # Atribuição automática seguindo o padrão ZP{element_id}
            assignment = f"ZP{element_id}"
            element = ElementConfig(element_id, "CountingHead", assignment)
            self.current_generator.add_element(element)
            self.update_elements_tree()
            self._mark_content_changed()
            
    def _normalize_element_id(self, element_id):
        """
        Normaliza Element ID para garantir 4 dígitos mínimos, adicionando zeros à esquerda
        
        Exemplos:
        - 1 → 0001
        - 30 → 0030  
        - 90 → 0090
        - 1234 → 1234 (já tem 4 dígitos)
        - 12345 → 12345 (mais de 4 dígitos, mantém)
        
        Args:
            element_id: ID original (int ou str)
            
        Returns:
            str: ID normalizado com pelo menos 4 dígitos
        """
        try:
            # Converter para int primeiro para validar
            id_num = int(element_id)
            
            # Converter para string com padding de zeros (mínimo 4 dígitos)
            normalized = f"{id_num:04d}"
            
            return int(normalized)  # Retornar como int para compatibilidade
            
        except (ValueError, TypeError) as e:
            print(f"Erro ao normalizar Element ID '{element_id}': {e}")
            # Em caso de erro, tentar retornar o valor original
            try:
                return int(element_id)
            except:
                return 1  # Fallback seguro

    def add_track_section(self):
        """Adiciona ambas TrackSections (1 e 2) simultaneamente com opção VAGO"""
        # Criar janela principal
        dialog = tk.Toplevel(self.root)
        dialog.title("Adicionar TrackSections")
        dialog.geometry("400x220")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Centralizar janela
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (240)
        y = (dialog.winfo_screenheight() // 2) - (210)
        dialog.geometry(f"480x420+{x}+{y}")
        
        # Variáveis
        element_id_var = tk.StringVar()
        assignment1_var = tk.StringVar()
        assignment2_var = tk.StringVar()
        vago_var = tk.BooleanVar()
        
        # Frame principal com padding
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = ttk.Label(main_frame, text="Configuração de TrackSections", 
                               font=("Arial", 12, "bold"))
        title_label.pack(pady=(0, 15))
        
        # Frame para Element ID
        id_frame = ttk.Frame(main_frame)
        id_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(id_frame, text="Element ID:").pack(side=tk.LEFT)
        element_id_entry = ttk.Entry(id_frame, textvariable=element_id_var, width=15)
        element_id_entry.pack(side=tk.LEFT, padx=(10, 0))
        element_id_entry.focus()
        
        # Frame para TrackSection1
        ts1_frame = ttk.LabelFrame(main_frame, text="TrackSection1", padding="10")
        ts1_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(ts1_frame, text="Atribuição:").pack(side=tk.LEFT)
        assignment1_entry = ttk.Entry(ts1_frame, textvariable=assignment1_var, width=20)
        assignment1_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # Frame para TrackSection2
        ts2_frame = ttk.LabelFrame(main_frame, text="TrackSection2", padding="10")
        ts2_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(ts2_frame, text="Atribuição:").pack(side=tk.LEFT)
        assignment2_entry = ttk.Entry(ts2_frame, textvariable=assignment2_var, width=20)
        assignment2_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # Checkbox para VAGO
        vago_check = ttk.Checkbutton(ts2_frame, text="VAGO (TrackSection2 não utilizada)", 
                                   variable=vago_var)
        vago_check.pack(pady=(10, 0))
        
        # Frame para botões
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Variável para resultado
        result = {'success': False}
        
        def on_vago_change():
            """Controla o estado do campo Assignment2 baseado no checkbox VAGO"""
            if vago_var.get():
                assignment2_var.set("VAGO")
                assignment2_entry.configure(state="disabled")
            else:
                if assignment2_var.get() == "VAGO":
                    assignment2_var.set("")
                assignment2_entry.configure(state="normal")
        
        # Conectar evento do checkbox
        vago_check.configure(command=on_vago_change)
        
        def on_ok():
            try:
                # Validar Element ID
                if int(element_id_var.get()) < 0:
                    messagebox.showerror("Erro", "Valores negativos não são aceitos")
                    return
                element_id_str = element_id_var.get().strip()
                for element in self.current_generator.elements:
                    if element.element_type in ["TrackSection1", "TrackSection2"] and str(element.element_id) == element_id_str:
                        messagebox.showerror("Erro", f"Já existe uma TrackSection com Element ID {element_id_str}!")
                        element_id_entry.focus()
                        return
                    
                if not element_id_str:
                    messagebox.showerror("Erro", "Element ID é obrigatório!")
                    element_id_entry.focus()
                    return
                
                try:
                    element_id_raw = int(element_id_str)
                except ValueError:
                    messagebox.showerror("Erro", "Element ID deve ser um número válido!")
                    element_id_entry.focus()
                    return
                # Normalizar ID
                element_id = self._normalize_element_id(element_id_raw)
                # Validar Assignment1
                assignment1 = assignment1_var.get().strip().upper()
                if not assignment1 or assignment1 == "ex: 1AT, 1BT, MAT":
                    messagebox.showerror("Erro", "Assignment da TrackSection1 é obrigatório!\nDigite um valor válido.")
                    assignment1_entry.focus()
                    return
                
                # Validar Assignment2 (só se não for VAGO)
                assignment2 = assignment2_var.get().strip().upper()
                if not vago_var.get() and (not assignment2 or assignment2 == "ex: 2AT, 2BT, MBT"):
                    messagebox.showerror("Erro", "Assignment da TrackSection2 é obrigatório!\n(ou marque VAGO)")
                    assignment2_entry.focus()
                    return
                
                # Se VAGO estiver marcado, definir assignment2 como "VAGO"
                if vago_var.get():
                    assignment2 = "VAGO"
                
                # Criar ambas TrackSections
                element1 = ElementConfig(element_id, "TrackSection1", assignment1)
                element2 = ElementConfig(element_id, "TrackSection2", assignment2)
                
                self.current_generator.add_element(element1)
                self.current_generator.add_element(element2)
                self.update_elements_tree()
                
                result['success'] = True
                dialog.destroy()
                
                # Mostrar confirmação
                messagebox.showinfo("Sucesso", 
                    f"TrackSections adicionadas com sucesso!\n\n"
                    f"Element ID: {element_id}\n"
                    f"TrackSection1: {assignment1}\n"
                    f"TrackSection2: {assignment2}")
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao adicionar TrackSections:\n{str(e)}")
        
        def on_cancel():
            result['success'] = False
            dialog.destroy()
        
        # Botões
        ttk.Button(button_frame, text="✓ Adicionar Ambas", command=on_ok, width=20).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="✗ Cancelar", command=on_cancel, width=12).pack(side=tk.RIGHT)
        
        # Atalhos de teclado
        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())
        
        # Placeholder text para assignments
        def setup_placeholder(entry, var, placeholder_text):
            def on_focus_in(event):
                if var.get() == placeholder_text:
                    var.set("")
                    entry.configure(foreground="black")
            
            def on_focus_out(event):
                if not var.get():
                    var.set(placeholder_text)
                    entry.configure(foreground="gray")
            
            def on_key_press(event):
                # Limpar placeholder quando o usuário começar a digitar
                # Mas só se não for uma tecla de controle
                if event.keysym not in ['Return', 'Tab', 'Escape', 'Left', 'Right', 'Up', 'Down']:
                    if var.get() == placeholder_text:
                        var.set("")
                        entry.configure(foreground="black")
            
            var.set(placeholder_text)
            entry.configure(foreground="gray")
            entry.bind('<FocusIn>', on_focus_in)
            entry.bind('<FocusOut>', on_focus_out)
            entry.bind('<KeyPress>', on_key_press)

        # Aguardar resultado
        dialog.wait_window()
    
    def remove_elements(self):
        """Remove um elemento selecionado"""
        selection = self.elements_tree.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Nenhum elemento selecionado para remoção!")
            return
        try:
            for elements in selection:
                item = self.elements_tree.item(elements)
                values = item['values']
                
                if not values or len(values) < 3:
                    messagebox.showerror("Erro", "Dados do elemento inválidos!")
                    return
                
                # Converter valores da árvore para os tipos corretos
                selected_element_id = int(values[0])  # element_id é int
                selected_element_type = str(values[1])  # element_type é string
                selected_element_assignment = str(values[2])  # element_assignment é string
                
                # Encontrar e remover o elemento
                element_found = False
                for i, element in enumerate(self.current_generator.elements):
                    if (element.element_id == selected_element_id and 
                        element.element_type == selected_element_type and 
                        element.element_assignment == selected_element_assignment):
                        del self.current_generator.elements[i]
                        element_found = True
                        break
                
                if element_found:
                    messagebox.showinfo("Sucesso", f"Elemento removido:\n"
                                                f"Element ID: {selected_element_id}\n"
                                                f"Tipo: {selected_element_type}\n"
                                                f"Atribuição: {selected_element_assignment}")
                else:
                    messagebox.showerror("Erro", "Elemento não encontrado na lista!")
        
            self.update_elements_tree()
            self._mark_content_changed()
                
        except ValueError as e:
            messagebox.showerror("Erro", f"Erro de conversão de dados: {e}")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao remover elemento: {e}")

    def clear_all_elements(self):
        """Remove todos os elementos da lista"""
        if not self.current_generator or not self.current_generator.elements:
            messagebox.showinfo("Aviso", "Não há elementos para remover!")
            return
        
        # Confirmar ação
        total_elements = len(self.current_generator.elements)
        response = messagebox.askyesno(
            "Confirmar Limpeza", 
            f"Deseja realmente remover todos os {total_elements} elementos?\n\n"
            "Esta ação não pode ser desfeita!"
        )
        
        if response:
            try:
                # Limpar todos os elementos
                self.current_generator.elements.clear()
                self.update_elements_tree()
                self._mark_content_changed()
                
                messagebox.showinfo("Sucesso", 
                    f"Todos os elementos foram removidos!\n"
                    f"Total removido: {total_elements} elementos")
                    
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao limpar elementos: {e}")
    
    def update_angle_options(self, *args):
        """Atualiza as opções de ângulo baseado na ferramenta selecionada"""
        tool = self.tool_var.get()
        
        # Configurações específicas por ferramenta (baseado nas imagens disponíveis)
        tool_configs = {
            "rail": {
                "angles": ["0", "45", "90", "180", "225", "270", "315"],
                "mirror_enabled": True,
                "mirror_fixed_angles": ["0", "180"]  # Ângulos que têm mirror fixo em 0
            },
            "switch": {
                "angles": ["0", "45", "90", "180", "225"],
                "mirror_enabled": True,
                "mirror_fixed_angles": []  # Todos os ângulos permitem mirror
            },
            "crossing": {
                "angles": ["0", "90", "270"],
                "mirror_enabled": False,
                "mirror_fixed_angles": []  # Mirror sempre 0
            },
            "sensor": {
                "angles": ["0", "45", "90", "135", "180", "225", "270", "315"],
                "mirror_enabled": False,
                "mirror_fixed_angles": []  # Mirror sempre 0
            },
            "link": {
                "angles": ["0", "90", "180", "270"],
                "mirror_enabled": False,
                "mirror_fixed_angles": []  # Mirror sempre 0
            },
            "fma": {
                "angles": ["0", "90", "180", "270"],
                "mirror_enabled": False,
                "mirror_fixed_angles": []  # Mirror sempre 0
            }
        }
        
        # Obter configuração da ferramenta atual
        config = tool_configs.get(tool, {
            "angles": ["0", "45", "90", "135", "180", "225", "270", "315"],
            "mirror_enabled": False,
            "mirror_fixed_angles": []
        })
        
        angles = config["angles"]
        
        # Atualizar lista de ângulos disponíveis
        self.angle_combo['values'] = angles
        
        # Validar ângulo atual
        current_angle = self.angle_var.get()
        if current_angle not in angles:
            self.angle_var.set(angles[0])
            current_angle = angles[0]
        
        # Configurar estado do mirror
        if config["mirror_enabled"]:
            # Mirror é possível para esta ferramenta
            if current_angle in config["mirror_fixed_angles"]:
                # Ângulo específico que não permite mirror
                self.mirror_combo['state'] = "disabled"
                self.mirror_var.set("0")
            else:
                # Ângulo que permite mirror
                self.mirror_combo['state'] = "readonly"
        else:
            # Ferramenta não usa mirror
            self.mirror_combo['state'] = "disabled"
            self.mirror_var.set("0")
        
        # Remover trace anterior para evitar duplicação
        try:
            self.angle_var.trace_remove("write", self.update_mirror_state)
        except:
            pass
        
        # Adicionar trace para atualizar mirror quando ângulo muda
        self.angle_var.trace_add("write", self.update_mirror_state)
    
    def update_mirror_state(self, *args):
        """Atualiza o estado do mirror baseado no ângulo selecionado para ferramentas que suportam mirror"""
        tool = self.tool_var.get()
        angle = self.angle_var.get()
        
        # Configurações de mirror por ferramenta
        if tool == "rail":
            # Rails: 0° e 180° têm mirror fixo em 0
            if angle in ["0", "180"]:
                self.mirror_combo['state'] = "disabled"
                self.mirror_var.set("0")
            else:
                self.mirror_combo['state'] = "readonly"
        elif tool == "switch":
            # Switches: todos os ângulos permitem mirror
            self.mirror_combo['state'] = "readonly"
        else:
            # Outras ferramentas: mirror sempre desabilitado
            self.mirror_combo['state'] = "disabled"
            self.mirror_var.set("0")
    
    def coord_to_excel(self, x, y):
        """Converte coordenadas numéricas para formato de grade (0,0) -> (0,0)"""
        return f"({x},{y})"
    
    def on_canvas_click(self, event):
        """Evento de clique no canvas"""
        x = self.trackplan_canvas.canvasx(event.x)
        y = self.trackplan_canvas.canvasy(event.y)
        
        # Converter para coordenadas da grade (ajustar para espaço reservado das coordenadas)
        grid_x = int((x - self.grid_size) // self.grid_size)
        grid_y = int((y - self.grid_size) // self.grid_size)
        
        # Verificar se está dentro da grade válida (0 até width, 0 até height)
        try:
            width = int(self.width_var.get())
            height = int(self.height_var.get())
        except ValueError:
            width, height = 71, 16
        
        if grid_x < 0 or grid_y < 0 or grid_x > width or grid_y > height:
            return
        
        # Interceptar modo de seleção de trilhos para FMA
        if getattr(self, '_fma_rail_pick_mode', False):
            self._fma_pick_handle_click(grid_x, grid_y)
            return

        tool = self.tool_var.get()
        
        # Ferramenta de seleção
        if tool == "select":
            self.handle_selection_click(grid_x, grid_y, event)
            return
        
        if not tool == "select":
            self.clear_selection()
        
        # Salvar estado antes de fazer qualquer mudança
        self.save_state_for_undo()
        
        # Borracha não precisa de ângulo ou mirror
        if tool == "eraser":
            self.remove_element_at_position(grid_x, grid_y)
            return
    
        if not hasattr(self, 'fma_type_var'):
            self.fma_type_var = tk.BooleanVar(value=True)

        # Para outras ferramentas, obter ângulo e mirror
        angle = int(self.angle_var.get())
        mirror = int(self.mirror_var.get())
        
        if tool == "rail":
            self.save_state_for_undo()
            self.add_rail_element(grid_x, grid_y, angle, mirror)
        elif tool == "link":
            url = self.link_ideia(pick_only=True)
            if not url:
                return
            self.save_state_for_undo()
            self.add_link_element(grid_x, grid_y, angle, url)
        elif tool == "switch":
            self.save_state_for_undo()
            self.add_switch_element(grid_x, grid_y, angle, mirror)
        elif tool == "sensor":
            self.save_state_for_undo()
            self.add_sensor_element(grid_x, grid_y, angle)
        elif tool == "fma":
            fma_type = 'FMA1' if self.fma_type_var.get() else 'FMA2'
            self.save_state_for_undo()
            self.add_fma_element(grid_x, grid_y, angle, None, fma_type)
        elif tool == "crossing":
            self.save_state_for_undo()
            self.add_crossing_element(grid_x, grid_y, angle)

        self.refresh_fma_test_window()

    def _apply_url_to_selected_links(self, url: str):
        """Aplica URL (normalizada) aos links selecionados no trackplan."""
        link_elements = [
            e for e in getattr(self, "selected_elements", [])
            if isinstance(e, dict) and e.get("type") == "link"
        ]
        if not link_elements:
            messagebox.showwarning("Aviso", "Selecione ao menos 1 elemento do tipo Link no Trackplan.")
            return False

        url = (url or "").strip()
        if not url:
            messagebox.showwarning("Aviso", "URL/IP vazio.")
            return False

        # Normalizar (igual ao save_link_url)
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "http://" + url

        # Um snapshot por operação (não por link) — mais amigável no Ctrl+Z
        self.save_state_for_undo()

        for link in link_elements:
            link["url"] = url

        self._mark_content_changed()
        messagebox.showinfo("Sucesso", f"URL aplicada em {len(link_elements)} link(s):\n{url}")
        return True

    def link_ideia(self, pick_only: bool=False):
        """Abre a janela de configuração de Link Ideia"""
        if not hasattr(self, "_ip_entries"):
            self._ip_entries = []

        if not pick_only:
            # Exigir seleção de Link (modo aplicar)
            link_elements = [
                e for e in getattr(self, "selected_elements", [])
                if isinstance(e, dict) and e.get("type") == "link"
            ]
            if not link_elements:
                messagebox.showwarning("Aviso", "Selecione um Link no Trackplan antes de usar 'Link Ideia'.")
                return None

        options = []
        for ip_fds, ip_fadc, desc, tem_fds in self._ip_entries:
            ip_fds = str(ip_fds).strip()
            ip_fadc = str(ip_fadc).strip()
            desc = str(desc).strip()
            tem_fds = bool(tem_fds)
            if not ip_fds or not ip_fadc:
                continue
            label = f"{ip_fds}  —  {desc}" if desc else ip_fds
            options.append((label, ip_fds))

        link_window = tk.Toplevel(self.root)
        link_window.title("Configuração de Link Ideia")
        link_window.transient(self.root)
        link_window.grab_set()
        link_window.resizable(False, False)

        # Centralizar
        link_window.update_idletasks()
        w, h = 520, 300
        x = (link_window.winfo_screenwidth() // 2) - (w // 2)
        y = (link_window.winfo_screenheight() // 2) - (h // 2)
        link_window.geometry(f"{w}x{h}+{x}+{y}")

        main = ttk.Frame(link_window, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        title = "Escolha o destino do Link" if pick_only else "Aplicar destino em Link(s) selecionado(s)"
        ttk.Label(main, text=title, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 10))

        select_frame = ttk.LabelFrame(main, text="Destino", padding=10)
        select_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(select_frame, text="Escolha um IP cadastrado:").grid(row=0, column=0, sticky="w")

        selected_label_var = tk.StringVar(value=options[0][0] if options else "")
        combo = ttk.Combobox(
            select_frame,
            textvariable=selected_label_var,
            values=[lbl for (lbl, _ip) in options],
            state="readonly",
            width=55
        )
        combo.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        select_frame.grid_columnconfigure(0, weight=1)

        ttk.Label(select_frame, text="Ou digite manualmente:").grid(row=2, column=0, sticky="w", pady=(10, 0))
        manual_var = tk.StringVar(value="")
        manual_entry = ttk.Entry(select_frame, textvariable=manual_var, width=40)
        manual_entry.grid(row=3, column=0, sticky="ew", pady=(6, 0))

        opts = ttk.Frame(main)
        opts.pack(fill=tk.X, pady=(0, 10))

        add_http_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Adicionar http:// automaticamente", variable=add_http_var).pack(anchor="w")

        preview_var = tk.StringVar(value="")
        ttk.Label(main, textvariable=preview_var, foreground="gray").pack(anchor="w", pady=(0, 10))

        result = {"url": None}

        def compute_url_preview():
            manual = (manual_var.get() or "").strip()
            if manual:
                raw = manual
            else:
                chosen = (selected_label_var.get() or "").strip()
                raw = ""
                for lbl, ip in options:
                    if lbl == chosen:
                        raw = ip
                        break

            if not raw:
                preview_var.set("Preview: (nenhum destino selecionado)")
                return ""

            url = raw
            if add_http_var.get() and not (url.startswith("http://") or url.startswith("https://")):
                url = "http://" + url
            preview_var.set(f"Preview: {url}")
            return url

        def on_apply():
            url = compute_url_preview()
            if not url:
                messagebox.showwarning("Aviso", "Selecione/digite um destino válido.")
                return

            if pick_only:
                result["url"] = url
                link_window.destroy()
                return

            # modo aplicar em seleção
            if self._apply_url_to_selected_links(url):
                link_window.destroy()

        manual_var.trace_add("write", lambda *_: compute_url_preview())
        selected_label_var.trace_add("write", lambda *_: compute_url_preview())
        add_http_var.trace_add("write", lambda *_: compute_url_preview())
        compute_url_preview()

        buttons = ttk.Frame(main)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="Aplicar", command=on_apply).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(buttons, text="Cancelar", command=link_window.destroy).pack(side=tk.RIGHT)

        link_window.bind("<Return>", lambda e: on_apply())
        link_window.bind("<Escape>", lambda e: link_window.destroy())

        # Para pick_only, aguardar e devolver o resultado
        if pick_only:
            link_window.wait_window()
            return result["url"]

        return None

    def add_crossing_element(self, grid_x, grid_y, angle):
        """Adiciona um elemento 'crossing' (cruzamento). Ângulos: 0, 90, 270."""
        element_id = self.next_element_id

        if ((self.next_element_id + 1) == 8000):
            self.next_element_id = 71000
        else:
            self.next_element_id += 1       

        # Remover elemento existente na posição
        self.remove_element_at_position(grid_x, grid_y)

        # Posição no canvas (modo centralizado como demais)
        canvas_x = (grid_x + 1) * self.grid_size + self.grid_size // 2
        canvas_y = (grid_y + 1) * self.grid_size + self.grid_size // 2

        image_key = f"crossing_{angle}"
        element = {
            "type": "crossing",
            "id": element_id,
            "x": grid_x,
            "y": grid_y,
            "angle": angle,
        }

        # Usar imagem se existir; senão desenhar fallback com duas linhas
        if hasattr(self, 'element_images') and image_key in self.element_images:
            cid = self.trackplan_canvas.create_image(
                canvas_x, canvas_y,
                image=self.element_images[image_key],
                # usar tag 'rail' para reutilizar a limpeza existente
                tags=("rail", "crossing")
            )
            element["canvas_id"] = cid
            element["original_image_key"] = image_key
        else:
            half = self.grid_size // 2
            h_id = self.trackplan_canvas.create_line(
                canvas_x - half, canvas_y, canvas_x + half, canvas_y,
                fill="black", width=3, tags=("rail", "crossing")
            )
            v_id = self.trackplan_canvas.create_line(
                canvas_x, canvas_y - half, canvas_x, canvas_y + half,
                fill="black", width=3, tags=("rail", "crossing")
            )
            element["canvas_ids"] = [h_id, v_id]

        self.trackplan_elements.append(element)
        self._mark_content_changed()
        return element

    def add_rail_element(self, grid_x, grid_y, angle, mirror):
        """Adiciona um elemento de trilho"""
        element_id = self.next_element_id
        
        if ((self.next_element_id + 1) == 8000):
            self.next_element_id = 71000
        else:
            self.next_element_id += 1        
        # Remover elemento existente na mesma posição
        self.remove_element_at_position(grid_x, grid_y)
        
        # Calcular posição no canvas (ajustar para espaço reservado das coordenadas)
        canvas_x = (grid_x + 1) * self.grid_size + self.grid_size // 2
        canvas_y = (grid_y + 1) * self.grid_size + self.grid_size // 2
        
        # Verificar se existe imagem para este rail
        image_key = f"rail_{angle}_{mirror}"
            
        if hasattr(self, 'element_images') and image_key in self.element_images:
            # Usar imagem
            rail_id = self.trackplan_canvas.create_image(
                canvas_x, canvas_y, 
                image=self.element_images[image_key], 
                tags="rail"
            )
            rail_ids = [rail_id]
        else:
            # Usar desenho por linhas (método atual)
            # Para ângulos simples (0° e 180°), mirror é sempre 0 
            if not mirror:
                effective_mirror = 0
            else:
                effective_mirror = mirror
                
            line_coords_list = self.get_rail_line_coords(canvas_x, canvas_y, angle, effective_mirror)
            rail_ids = []
            
            for line_coords in line_coords_list:
                rail_id = self.trackplan_canvas.create_line(*line_coords, fill="black", width=3, tags="rail")
                rail_ids.append(rail_id)
        
        # Adicionar aos elementos
        rail_element = {
            "type": "rail",
            "id": element_id,
            "x": grid_x,
            "y": grid_y,
            "canvas_ids": rail_ids,  # Múltiplos IDs para estruturas compostas
            "canvas_id": rail_ids[0] if rail_ids else None,  # ID principal para destacamento
            "angle": angle,
            "mirror": mirror,
            "rail_type": None,
            "original_image_key": image_key if hasattr(self, 'element_images') and image_key in self.element_images else None
        }
        
        self.trackplan_elements.append(rail_element)
        self._mark_content_changed()
        return rail_element  # Retornar o elemento criado
    
    def add_switch_element(self, grid_x, grid_y, angle, mirror):
        """Adiciona um elemento switch"""

        element_id = self.next_element_id
        
        if ((self.next_element_id + 1) == 8000):
            self.next_element_id = 71000
        else:
            self.next_element_id += 1
        
        # Remover elemento existente na mesma posição
        self.remove_element_at_position(grid_x, grid_y)
        
        # Calcular posição no canvas (ajustar para espaço reservado das coordenadas)
        canvas_x = (grid_x + 1) * self.grid_size + self.grid_size // 2
        canvas_y = (grid_y + 1) * self.grid_size + self.grid_size // 2
        
        # Verificar se existe imagem para este switch
        image_key = f"switch_{angle}_{mirror}"
        if hasattr(self, 'element_images') and image_key in self.element_images:
            # Usar imagem
            main_id = self.trackplan_canvas.create_image(
                canvas_x, canvas_y, 
                image=self.element_images[image_key], 
                tags="switch"
            )
            diag_id = None  # Imagem já inclui diagonal
        else:
            # Usar desenho por linhas (método atual)
            main_line, diag_line = self.get_switch_coords(canvas_x, canvas_y, angle, mirror)
            
            main_id = self.trackplan_canvas.create_line(*main_line, fill="black", width=3, tags="switch")
            diag_id = self.trackplan_canvas.create_line(*diag_line, fill="blue", width=2, tags="switch")
        
        # Adicionar aos elementos
        switch_element = {
            "type": "switch",
            "id": element_id,
            "x": grid_x,
            "y": grid_y,
            "canvas_id": main_id,
            "diag_id": diag_id,
            "angle": angle,
            "mirror": mirror,
            "rail_type": "SWITCH",  # Manter para compatibilidade com sistema dual
            "original_image_key": image_key if hasattr(self, 'element_images') and image_key in self.element_images else None
        }
        
        self.trackplan_elements.append(switch_element)
        self._mark_content_changed()
        return switch_element  # Retornar o elemento criado
    
    def add_sensor_element(self, grid_x, grid_y, angle, mirror=None, preserve_id=None):
        """Adiciona um elemento sensor com rail automático correspondente.
        Parâmetros:
        - grid_x, grid_y: posição no grid
        - angle: ângulo do sensor
        - mirror: opcional (0=left, 1=right). Quando fornecido, define também a posição do sensor.
        """
        if preserve_id is not None:
            element_id = preserve_id
        else:
            element_id = self.next_sensor_id
            self.next_sensor_id += 1
        
        # Remover elemento existente na mesma posição (exceto rails automáticos)
        self.remove_element_at_position(grid_x, grid_y, preserve_auto_rails=True)
        
        # Calcular posição no canvas (ajustar para espaço reservado das coordenadas)
        canvas_x = (grid_x + 1) * self.grid_size + self.grid_size // 2
        canvas_y = (grid_y + 1) * self.grid_size + self.grid_size // 2
        
    # Verificar se existe imagem para este sensor (formato padrão sem direção)
        image_key = f"sensor_{angle}"
        
        if hasattr(self, 'element_images') and image_key in self.element_images:
            # Usar imagem normal (sem direção)
            line_id = self.trackplan_canvas.create_image(
                canvas_x, canvas_y, 
                image=self.element_images[image_key], 
                tags="sensor"
            )
            symbol_id = None  # Imagem já inclui símbolo
        else:
            # Usar desenho por linhas (método atual)
            line_coords = self.get_sensor_line_coords(canvas_x, canvas_y, angle)
            symbol_coords = self.get_sensor_symbol_coords(canvas_x, canvas_y, angle)
            
            line_id = self.trackplan_canvas.create_line(*line_coords, fill="red", width=2, tags="sensor")
            symbol_id = self.trackplan_canvas.create_oval(*symbol_coords, fill="red", outline="red", tags="sensor")
        
        # Adicionar aos elementos
        sensor_element = {
            "type": "sensor",
            "id": element_id,
            "x": grid_x,
            "y": grid_y,
            "canvas_id": line_id,
            "symbol_id": symbol_id,
            "name": f"ZP{element_id}",
            "ref_id": element_id + 10000,
            "angle": angle,
            "original_image_key": image_key if hasattr(self, 'element_images') and image_key in self.element_images else None
        }

        # Se o parâmetro mirror foi informado, armazenar e definir a posição
        if mirror is not None:
            try:
                mval = int(mirror)
            except Exception:
                mval = 1 if str(mirror).lower() in ("1", "true", "right") else 0
            sensor_element["mirror"] = mval
            sensor_element["position"] = "left" if mval == 0 else "right"
        
        self.trackplan_elements.append(sensor_element)
        
        # Verificar se já existe rail automático na posição (contexto de carregamento)
        existing_auto_rail = None
        for element in self.trackplan_elements:
            if (element.get("type") == "rail" and 
                element.get("x") == grid_x and 
                element.get("y") == grid_y and
                element.get("auto_rail") == True):
                existing_auto_rail = element
                break
        
        if not existing_auto_rail:
            # Adicionar rail automático correspondente apenas se não existe
            auto_rail = self.add_automatic_rail_for_element(grid_x, grid_y, "sensor", angle, element_id)
            
            if auto_rail:
                sensor_element["auto_rail_id"] = auto_rail.get("id")
        else:
            sensor_element["auto_rail_id"] = existing_auto_rail.get("id")
        
        # Aplicar alteração
        self._mark_content_changed()
        return sensor_element  # Retornar o elemento criado

    def add_link_element(self, grid_x, grid_y, angle, url):
        """Adiciona um elemento Link"""
        element_id = self.next_element_id
        
        if ((self.next_element_id + 1) == 8000):
            element_id = 71000
        else:
            self.next_element_id += 1

        # Remover elemento existente na mesma posição
        self.remove_element_at_position(grid_x, grid_y)

        # Calcular posição no canvas
        canvas_x = (grid_x + 1) * self.grid_size + self.grid_size // 2
        canvas_y = (grid_y + 1) * self.grid_size + self.grid_size // 2

        # Carregar imagem da seta conforme o ângulo
        image_key = f"link_{angle}"
        if hasattr(self, 'element_images') and image_key in self.element_images:
            link_id = self.trackplan_canvas.create_image(
                canvas_x, canvas_y,
                image=self.element_images[image_key],
                tags="link"
            )
        else:
            # Fallback: desenhar uma seta simples
            link_id = self.trackplan_canvas.create_line(
                canvas_x - 10, canvas_y, canvas_x + 10, canvas_y,
                arrow=tk.LAST, fill="blue", width=3, tags="link"
            )

        # Normalizar e validar a URL para evitar duplicação de "http://"
        normalized_url = url.strip() if url else ""
        if normalized_url and not (normalized_url.startswith("http://") or normalized_url.startswith("https://")):
            normalized_url = f"http://{normalized_url}"

        # Adicionar aos elementos
        link_element = {
            "type": "link",
            "id": element_id,
            "x": grid_x,
            "y": grid_y,
            "angle": angle,
            "url": normalized_url,
            "canvas_id": link_id
        }
        self.trackplan_elements.append(link_element)
        self._mark_content_changed()
        return link_element

    def update_sensor_fma_associations(self):
        """Atualiza automaticamente as associações fma0/fma1 de todos os sensores baseado nas FMAs existentes.
        Regra:
        - fma0: IDs iniciando por '3' para o mesmo refId do sensor
        - fma1: IDs iniciando por '4' para o mesmo refId do sensor
        - Match principal por FMA.ref_id == Sensor.id; fallback por FMA.ref_id == Sensor.ref_id
        """
        try:
            if not hasattr(self, 'trackplan_elements'):
                return

            sensors = [e for e in self.trackplan_elements if e.get("type") == "sensor"]
            fmas = [e for e in self.trackplan_elements if e.get("type") == "fma"]

            # Indexar FMAs por refId normalizado
            fmas_by_ref = {}
            for fma in fmas:
                fid = str(fma.get("id", "")).strip()
                ref = str(fma.get("ref_id", "")).strip()
                if not fid or not ref:
                    continue
                ref_norm = str(int(ref)) if ref.isdigit() else ref
                bucket = fmas_by_ref.setdefault(ref_norm, {"3": None, "4": None})
                if fid.startswith("3"):
                    bucket["3"] = fid
                elif fid.startswith("4"):
                    bucket["4"] = fid

            for sensor in sensors:
                sensor_id_raw = str(sensor.get("id", "")).strip()
                sensor_ref_raw = str(sensor.get("ref_id", "")).strip()
                sid = str(int(sensor_id_raw)) if sensor_id_raw.isdigit() else sensor_id_raw
                sref = str(int(sensor_ref_raw)) if sensor_ref_raw.isdigit() else sensor_ref_raw

                # Valores já definidos (ex.: pelo checkbox)
                existing_fma0 = sensor.get("fma0")
                existing_fma1 = sensor.get("fma1")

                bucket = fmas_by_ref.get(sid) or fmas_by_ref.get(sref)
                if bucket:
                    if bucket.get("3"):
                        sensor["fma0"] = bucket["3"]
                    elif existing_fma0:
                        sensor["fma0"] = existing_fma0
                    else:
                        sensor.pop("fma0", None)

                    if bucket.get("4"):
                        sensor["fma1"] = bucket["4"]
                    elif existing_fma1:
                        sensor["fma1"] = existing_fma1
                    else:
                        sensor.pop("fma1", None)

                else:
                    if existing_fma0:
                        sensor["fma0"] = existing_fma0
                    else:
                        sensor.pop("fma0", None)
                    
                    if existing_fma1:
                        sensor["fma1"] = existing_fma1
                    else:
                        sensor.pop("fma1", None)

        except Exception as e:
            print(f"Erro ao atualizar associações sensor-FMA: {e}")

    def compute_fma_ids_for_sensor(self, sensor_id: str):
        """Retorna (fma0_id, fma1_id) a partir do ID do sensor. Ex.: 21230 -> (31230, 41230)."""
        s = str(sensor_id).strip()
        if not s:
            return None, None
        base = s[1:] if s.startswith('2') and len(s) > 1 else s
        return f"3{base}", f"4{base}"

    def ensure_sensor_fmas(self, sensor_element, has_fma, old_id=None):
        """Cria/atualiza/remove FMAs padrão fma0/fma1 para um sensor, apenas em memória.
        - fma0: prefixo 3 + sufixo do sensor (ex: 21230 -> 31230)
        - fma1: prefixo 4 + sufixo do sensor (ex: 21230 -> 41230)
        """
        try:
            if sensor_element is None:
                return
            sid = str(sensor_element.get('id', '')).strip()
            if not sid:
                print("ensure_sensor_fmas: sensor sem ID")
                return

            new_fma0_id, new_fma1_id = self.compute_fma_ids_for_sensor(sid)

            if has_fma:
                sensor_element['fma0'] = new_fma0_id
                sensor_element['fma1'] = new_fma1_id
            else:
                sensor_element.pop('fma0', None)
                sensor_element.pop('fma1', None)

            # Não chamar criação/remoção de FMAs na lista. Apenas manter associações coerentes.
            try:
                self.update_sensor_fma_associations()
            except Exception:
                pass

        except Exception as e:
            print(f"ensure_sensor_fmas: {e}")

    def _upsert_code_only_fma(self, fma_id, fallback_id, x, y, angle, name, ref_id):
        """Cria ou atualiza uma FMA em memória (sem canvas). Se existir com fallback_id, renomeia."""
        if not hasattr(self, 'trackplan_elements'):
            self.trackplan_elements = []
        fma = self.find_fma_by_id(fma_id) or (self.find_fma_by_id(fallback_id) if fallback_id else None)
        if fma:
            fma['id'] = str(fma_id)
            fma['x'] = x
            fma['y'] = y
            fma['angle'] = angle
            fma['name'] = name
            fma['ref_id'] = str(ref_id)
            fma['fma_type'] = 'FMA1' if str(fma_id).startswith('3') else 'FMA2'
        else:
            self.trackplan_elements.append({
                'type': 'fma',
                'id': str(fma_id),
                'x': x,
                'y': y,
                'angle': angle,
                'name': name,
                'ref_id': str(ref_id),
                'fma_type': 'FMA1' if str(fma_id).startswith('3') else 'FMA2',
                'canvas_id': None,
                'box_id': None,
                'text_id': None,
                'image_key': None
            })

    def _remove_fma_by_id(self, fma_id):
        """Remove uma FMA do trackplan_elements pelo ID (e do canvas se tiver)."""
        if not hasattr(self, 'trackplan_elements'):
            return
        for e in list(self.trackplan_elements):
            if e.get('type') == 'fma' and str(e.get('id')) == str(fma_id):
                try:
                    self.delete_element_completely(e)
                except Exception:
                    pass
                try:
                    self.trackplan_elements.remove(e)
                except ValueError:
                    pass
                break

    def find_fma_by_id(self, fma_id):
        """Busca FMA pelo id na lista de elementos."""
        if not fma_id or not hasattr(self, 'trackplan_elements'):
            return None
        for e in self.trackplan_elements:
            if e.get('type') == 'fma' and str(e.get('id')) == str(fma_id):
                return e
        return None

    def on_sensor_has_fma_toggle(self):
        """Callback para alternância do checkbox 'Possui FMA?' em editor de sensor."""
        try:
            sensor = getattr(self, 'current_sensor_element', None)
            var = getattr(self, 'sensor_has_fma_var', None)
            if sensor is None or var is None:
                return
            self.ensure_sensor_fmas(sensor, bool(var.get()))
        except Exception as e:
            print(f"on_sensor_has_fma_toggle: {e}")

    def add_fma_element(self, grid_x, grid_y, angle, name=None, fma_type='FMA1', ref_id=None):
        """Adiciona elemento FMA"""
        base_id = self.next_fma_id  # base pura
        # Gerar ID com prefixo
        element_id = base_id
        fma_name = name if name else f"FMA{base_id}"
        fma_ref_id = f"2{base_id-3000}"
        self.next_fma_id += 1

        # Remover elemento existente preservando auto rails
        self.remove_element_at_position(grid_x, grid_y, preserve_auto_rails=True)

        canvas_x = (grid_x + 1) * self.grid_size + self.grid_size // 2
        canvas_y = (grid_y + 1) * self.grid_size + self.grid_size // 2

        if not hasattr(self, 'element_images'):
            self.element_images = {}

        image_key = f"fma_{angle}_{fma_name}"
        if image_key not in self.element_images:
            img = self.create_fma_image_with_integrated_text(angle, fma_name)
            if img:
                self.element_images[image_key] = img

        if image_key in self.element_images:
            cid = self.trackplan_canvas.create_image(canvas_x, canvas_y,
                                                     image=self.element_images[image_key], tags="fma")
            fma_element = {
                "type": "fma",
                "id": element_id,
                "x": grid_x,
                "y": grid_y,
                "canvas_id": cid,
                "box_id": None,
                "text_id": None,
                "name": fma_name,
                "ref_id": fma_ref_id,
                "angle": angle,
                "fma_type": fma_type,
                "image_key": image_key,
                "associated_rails": [],
                "associated_sensors": []
            }
        else:
            # Fallback desenhado
            line_coords = self.get_fma_line_coords_full(canvas_x, canvas_y, angle)
            line_id = self.trackplan_canvas.create_line(*line_coords, fill="black", width=4, tags="fma")
            box_coords = self.get_fma_box_coords_by_angle(canvas_x, canvas_y, angle, fma_name)
            box_id = self.trackplan_canvas.create_rectangle(*box_coords, fill="white", outline="black", width=1, tags="fma")
            tx, ty = self.get_fma_text_position_in_box(box_coords)
            text_id = self.trackplan_canvas.create_text(tx, ty, text=fma_name,
                                                        font=("Arial", 6, "bold"), fill="black", tags="fma")
            fma_element = {
                "type": "fma",
                "id": element_id,
                "x": grid_x,
                "y": grid_y,
                "canvas_id": line_id,
                "box_id": box_id,
                "text_id": text_id,
                "name": fma_name,
                "ref_id": fma_ref_id,
                "angle": angle,
                "fma_type": fma_type,
                "associated_rails": [],
                "associated_sensors": []
            }

        self.trackplan_elements.append(fma_element)

        # Rail automático para FMA (memória apenas)
        auto_rail = None
        for e in self.trackplan_elements:
            if e.get("type") == "rail" and e.get("x") == grid_x and e.get("y") == grid_y and e.get("auto_rail"):
                auto_rail = e
                break
        if auto_rail:
            rail_id = str(auto_rail.get("id"))
            fma_element["auto_rail_id"] = rail_id
            fma_element["associated_rails"].append({"refId": rail_id, "auto": True})

        try:
            self.update_sensor_fma_associations()
        except:
            pass

        self._mark_content_changed()
        return fma_element
    
    def _find_sensor_at_or_near_position(self, x, y, radius=1):
        """Encontra sensor na posição exata ou próxima (dentro do raio)"""
        best = None
        best_dist = None
        for element in self.trackplan_elements:
            if element.get("type") == "sensor":
                sx = int(element.get("x", -999))
                sy = int(element.get("y", -999))
                if sx == x and sy == y:
                    return element
                dx = abs(sx - x)
                dy = abs(sy - y)
                if dx <= radius and dy <= radius:
                    d = dx + dy
                    if best_dist is None or d < best_dist:
                        best, best_dist = element, d
        return best
    
    def get_fma_line_coords_full(self, x, y, angle):
        """Calcula coordenadas da linha FMA de 4px correndo os 30px completos da célula - EXPANDIDO para todos os ângulos"""
        half_size = self.grid_size // 2  # 15 pixels (raio completo da célula)
        
        if angle == 0 or angle == 180:  # Horizontal - linha correndo toda a largura
            coords = [x - half_size, y, x + half_size, y]
        elif angle == 90 or angle == 270:  # Vertical - linha correndo toda a altura
            coords = [x, y - half_size, x, y + half_size]
        elif angle == 45 or angle == 225:  # Diagonal NE-SW
            coords = [x - half_size, y + half_size, x + half_size, y - half_size]
        elif angle == 135 or angle == 315:  # Diagonal NW-SE
            coords = [x - half_size, y - half_size, x + half_size, y + half_size]
        else:  # Padrão horizontal para ângulos não reconhecidos
            coords = [x - half_size, y, x + half_size, y]
        
        return coords
    
    def get_fma_box_coords_by_angle(self, x, y, angle, text):
        """Calcula coordenadas da caixa FMA posicionada de acordo com o ângulo - EXPANDIDO para todos os ângulos"""
        # Tamanho da caixa baseado no texto
        text_width = max(16, len(text) * 5)  # Mínimo 16px, 5px por caractere
        text_height = 10  # Altura fixa
        
        # Offset da linha (distância da caixa em relação à linha)
        offset = 8
        
        if angle == 0:  # Horizontal - caixa embaixo da linha
            box_x = x - text_width // 2
            box_y = y + offset
        elif angle == 45:  # Diagonal NE - caixa abaixo e à esquerda
            box_x = x - text_width - offset
            box_y = y + offset
        elif angle == 90:  # Vertical - caixa à direita da linha
            box_x = x + offset
            box_y = y - text_height // 2
        elif angle == 135:  # Diagonal SE - caixa à esquerda e acima
            box_x = x - text_width - offset
            box_y = y - text_height - offset
        elif angle == 180:  # Horizontal invertido - caixa acima da linha
            box_x = x - text_width // 2
            box_y = y - offset - text_height
        elif angle == 225:  # Diagonal SW - caixa à direita e acima
            box_x = x + offset
            box_y = y - text_height - offset
        elif angle == 270:  # Vertical invertido - caixa à esquerda da linha
            box_x = x - offset - text_width
            box_y = y - text_height // 2
        elif angle == 315:  # Diagonal NW - caixa à direita e abaixo
            box_x = x + offset
            box_y = y + offset
        else:  # Padrão - caixa embaixo
            box_x = x - text_width // 2
            box_y = y + offset
        
        return [box_x, box_y, box_x + text_width, box_y + text_height]
    
    def get_fma_text_position_in_box(self, box_coords):
        """Calcula posição centralizada do texto dentro da caixa"""
        # Centro da caixa
        text_x = (box_coords[0] + box_coords[2]) / 2
        text_y = (box_coords[1] + box_coords[3]) / 2
        
        return text_x, text_y
    
    def get_fma_text_coords_by_angle(self, x, y, angle):
        """Calcula as coordenadas do texto da FMA baseado no ângulo"""
        # Usar a mesma lógica da caixa, mas retornar apenas o centro
        box_coords = self.get_fma_box_coords_by_angle(x, y, angle, "FMA")  # Usar texto dummy
        text_x = (box_coords[0] + box_coords[2]) / 2
        text_y = (box_coords[1] + box_coords[3]) / 2
        return text_x, text_y
    
    def remove_element_at_position(self, grid_x, grid_y, preserve_auto_rails=False):
        """
        Remove elemento(s) existente(s) na posição especificada com controle avançado
        
        Args:
            grid_x, grid_y: Coordenadas da grade
            preserve_auto_rails: Se True, não remove rails automáticos (usado durante carregamento)
        """
        try:
            elements_to_remove = []
            elements_found = 0
            
            # Buscar todos os elementos na posição especificada
            for element in self.trackplan_elements:
                if element.get("x") == grid_x and element.get("y") == grid_y:
                    elements_found += 1
                    
                    # Verificar se deve preservar rails automáticos
                    if preserve_auto_rails and element.get("type") == "rail" and element.get("auto_rail"):
                        continue
                    
                    elements_to_remove.append(element)
            
            if elements_found == 0:
                return False
            
            # Remover elementos marcados
            removed_count = 0
            for element in elements_to_remove:
                # snapshot por item removido
                self.save_state_for_undo()

                # Verificar se é um sensor ou FMA com rail automático associado
                if element.get("type") in ["sensor", "fma"]:
                    self.remove_auto_rail_when_parent_deleted(element)
                
                # Remove associação em todas as FMAS antes de excluir
                self._dissociate_element_from_all_fmas(element)
                
                # Remover completamente do canvas e da lista
                self.delete_element_completely(element)
                
                # Remover da lista de elementos
                if element in self.trackplan_elements:
                    self.trackplan_elements.remove(element)
                    removed_count += 1
                
                # Remover da seleção se estiver selecionado
                if hasattr(self, 'selected_elements') and element in self.selected_elements:
                    self.selected_elements.remove(element)
            
            # Limpar mapa de posições
            position_key = f"{grid_x},{grid_y}"
            if hasattr(self, 'element_position_map') and position_key in self.element_position_map:
                del self.element_position_map[position_key]
                        
            # Atualizar informações de seleção
            if hasattr(self, 'update_selection_info'):
                self.update_selection_info()
            
            return removed_count > 0
            
        except Exception as e:
            print(f"Erro ao remover elemento na posição ({grid_x}, {grid_y}): {e}")
            traceback.print_exc()
            return False

    def remove_auto_rail_when_parent_deleted(self, deleted_element):
        """Remove rails automáticos quando o elemento pai (sensor/FMA) é deletado"""
        try:
            px, py = deleted_element.get('x'), deleted_element.get('y')
            pid = str(deleted_element.get('id', ''))
            ptype = deleted_element.get('type')

            to_remove = []
            for e in list(getattr(self, 'trackplan_elements', [])):
                if e.get('type') != 'rail' or not e.get('auto_rail'):
                    continue
                # heurísticas de vínculo: mesma célula OU referência direta ao pai (se existir)
                same_cell = (e.get('x') == px and e.get('y') == py)
                linked_by_id = (str(e.get('parentId', '')) == pid)
                linked_by_type = (e.get('parentType') == ptype)
                if same_cell or (linked_by_id and linked_by_type):
                    to_remove.append(e)

            for r in to_remove:
                self.delete_element_completely(r)
                try:
                    self.trackplan_elements.remove(r)
                except ValueError:
                    pass

        except Exception as e:
            print(f"Erro ao remover rails automáticos: {e}")

    def undo_action(self):
        """Desfaz a última ação"""
        try:
            if not hasattr(self, 'undo_stack') or not self.undo_stack:
                return
            
            # Garantir que redo_stack existe
            if not hasattr(self, 'redo_stack'):
                self.redo_stack = []
            
            # Salvar estado atual para redo
            current_state = self._build_clean_state()
            self.redo_stack.append(current_state)
            
            # Restaurar estado anterior
            previous_state = self.undo_stack.pop()
            self.restore_state(previous_state)
            self._mark_content_changed()
                        
        except Exception as e:
            print("Erro no undo")
            import traceback
            traceback.print_exc()
    
    def redo_action(self):
        """Refaz a última ação desfeita"""
        try:
            if not hasattr(self, 'redo_stack') or not self.redo_stack:
                return
            
            # Garantir que undo_stack existe
            if not hasattr(self, 'undo_stack'):
                self.undo_stack = []
            
            # Salvar estado atual para undo
            current_state = self._build_clean_state()
            self.undo_stack.append(current_state)
            
            # Restaurar estado do redo
            next_state = self.redo_stack.pop()
            self.restore_state(next_state)
            self._mark_content_changed()
                        
        except Exception as e:
            print(f"Erro no redo: {e}")
            import traceback
            traceback.print_exc()

    def restore_state(self, state):
        """Restaura um estado salvo do trackplan recriando objetos Tkinter"""
        try:            
            # Restaurar dimensões da grade 
            if 'grid_width' in state:
                self.width_var.set(state['grid_width'])
            if 'grid_height' in state:
                self.height_var.set(state['grid_height'])
            
            # Limpar canvas completamente
            canvas_tags = ["rail", "link", "sensor", "switch", "fma", "element", "crossing",
                        "selection_highlight", "row_highlight", "column_highlight"]
            for tag in canvas_tags:
                self.trackplan_canvas.delete(tag)
            
            # Limpar seleções
            if hasattr(self, 'selected_elements'):
                self.clear_selection()
            
            self.trackplan_elements = []
            
            for safe_element in state['elements']:
                # Recriar elemento com propriedades básicas
                restored_element = {}
                
                # Copiar todas as propriedades seguras
                for key, value in safe_element.items():
                    if not key.startswith('_saved_'):  # Ignorar propriedades especiais por enquanto
                        if isinstance(value, (list, dict)):
                            restored_element[key] = copy.deepcopy(value)
                        else:
                            restored_element[key] = value
                
                # *** RECUPERAR INFORMAÇÕES ESPECIAIS ***
                if '_saved_image_key' in safe_element:
                    restored_element['image_key'] = safe_element['_saved_image_key']
                
                if '_saved_fma_name' in safe_element:
                    restored_element['name'] = safe_element['_saved_fma_name']
                
                if '_saved_fma_angle' in safe_element:
                    restored_element['angle'] = safe_element['_saved_fma_angle']
                
                self.trackplan_elements.append(restored_element)
            
            # Restaurar next_element_id
            self.next_element_id = state['next_element_id']

            if 'element_position_map' in state:
                self.element_position_map = copy.deepcopy(state['element_position_map'])

            elements_redrawn = 0
            for element in self.trackplan_elements:
                try:
                    self.redraw_element(element)
                    elements_redrawn += 1
                except Exception as e:
                    print(f"Erro ao redesenhar {element.get('type', 'unknown')}: {e}")
            
            # Aplicar correções de visibilidade
            self._restore_rail_visibility_state()
            self._force_hide_auto_rails()
            
            # Aplicar grade se necessário
            if 'grid_width' in state or 'grid_height' in state:
                self.apply_grid()
                        
        except Exception as e:
            print(f"Erro ao restaurar estado: {e}")
            traceback.print_exc()

    def _restore_rail_visibility_state(self):
        """Restaura o estado de visibilidade dos rails após undo/redo"""
        try:
            # Mapear posições com sensores e FMAs
            sensor_fma_positions = set()

            for element in self.trackplan_elements:
                if element.get("type") in ["sensor", "fma"]:
                    pos = (element.get("x"), element.get("y"))
                    sensor_fma_positions.add(pos)

            # Verificar todos os rails e ocultar os que estão nas mesmas posições
            rails_hidden = 0
            rails_auto_hidden = 0

            for element in self.trackplan_elements:
                if element.get("type") == "rail":
                    rail_pos = (element.get("x"), element.get("y"))

                    # Verificar se é rail automático (pelo ID ou flag)
                    is_auto_rail = (
                        element.get("auto_rail", False) or
                        element.get("rail_type") == "AUTO" or
                        (element.get("id", 0) >= 6000 and element.get("id", 0) < 7000 and 
                         element.get("parent_element") is not None)  # Só considerar auto se tiver parent_element
                    )

                    # Se há sensor ou FMA na mesma posição, ocultar o rail
                    if rail_pos in sensor_fma_positions:
                        self._hide_rail_visual(element)
                        rails_hidden += 1

                        if is_auto_rail:
                            rails_auto_hidden += 1
                    elif is_auto_rail:
                        # Mesmo que não haja sobreposição, ocultar rails automáticos
                        self._hide_rail_visual(element)
                        rails_auto_hidden += 1

            self._clear_stale_highlights()

        except Exception as e:
            print(f"Erro ao restaurar visibilidade dos rails: {e}")
            import traceback
            traceback.print_exc()

    def _clear_stale_highlights(self):
        """Limpa highlights azuis que podem ter ficado presos após undo/redo"""
        try:
            highlights_cleared = 0

            # Percorrer todos os elementos e restaurar suas imagens originais
            for element in self.trackplan_elements:
                if element.get("type") in ["rail", "switch", "sensor", "fma", "link"]:
                    # Verificar se o elemento tem uma imagem original salva
                    if "original_image_key" in element and element["original_image_key"]:
                        try:
                            # Restaurar imagem original se existir
                            if hasattr(self, 'element_images') and element["original_image_key"] in self.element_images:
                                if "canvas_id" in element and element["canvas_id"]:
                                    self.trackplan_canvas.itemconfig(
                                        element["canvas_id"],
                                        image=self.element_images[element["original_image_key"]]
                                    )
                                    highlights_cleared += 1
                        except Exception as e:
                            print(f"Erro ao restaurar imagem de {element.get('type')} ID {element.get('id')}: {e}")

        except Exception as e:
            print(f"Erro ao limpar highlights residuais: {e}")

    def _force_hide_auto_rails(self):
        """Força a ocultação de todos os rails automáticos no canvas"""
        try:
            auto_rails_hidden = 0

            for element in self.trackplan_elements:
                if element.get("type") == "rail":
                    # Verificar se é rail automático
                    is_auto_rail = (
                        element.get("auto_rail", False) or
                        element.get("rail_type") == "AUTO" or
                        (element.get("id", 0) >= 6000 and element.get("id", 0) < 7000 and 
                         element.get("parent_element") is not None)  # Só considerar auto se tiver parent_element
                    )

                    if is_auto_rail:
                        self._hide_rail_visual(element)
                        auto_rails_hidden += 1
        except Exception as e:
            print(f"Erro ao forçar ocultação de rails automáticos: {e}")
            import traceback
            traceback.print_exc()
    
    def redraw_element(self, element):
        """Redesenha um elemento no canvas"""
        # Calcular posição no canvas
        canvas_x = (element["x"] + 1) * self.grid_size + self.grid_size // 2
        canvas_y = (element["y"] + 1) * self.grid_size + self.grid_size // 2
        
        if element["type"] == "rail":
            if element.get("rail_type") == "SWITCH":
                # Redesenhar switch - verificar se existe imagem primeiro
                image_key = f"switch_{element['angle']}_{element['mirror']}"
                if hasattr(self, 'element_images') and image_key in self.element_images:
                    # Usar imagem personalizada
                    main_id = self.trackplan_canvas.create_image(
                        canvas_x, canvas_y, 
                        image=self.element_images[image_key], 
                        tags="switch"
                    )
                    element["canvas_id"] = main_id
                    element["diag_id"] = None  # Imagem já inclui diagonal
                else:
                    # Usar desenho por código
                    main_line, diag_line = self.get_switch_coords(canvas_x, canvas_y, element["angle"], element["mirror"])
                    main_id = self.trackplan_canvas.create_line(*main_line, fill="black", width=3, tags="switch")
                    diag_id = self.trackplan_canvas.create_line(*diag_line, fill="blue", width=2, tags="switch")
                    element["canvas_id"] = main_id
                    element["diag_id"] = diag_id
            else:
                # Redesenhar rail normal - verificar se existe imagem primeiro
                angle = element["angle"]
                mirror = element["mirror"]
                image_key = f"rail_{angle}_{mirror}"
                if hasattr(self, 'element_images') and image_key in self.element_images:
                    # Usar imagem personalizada
                    rail_id = self.trackplan_canvas.create_image(
                        canvas_x, canvas_y, 
                        image=self.element_images[image_key], 
                        tags="rail"
                    )
                    element["canvas_ids"] = [rail_id]
                else:
                    # Usar desenho por código
                    line_coords_list = self.get_rail_line_coords(canvas_x, canvas_y, element["angle"], element["mirror"])
                    rail_ids = []
                    for line_coords in line_coords_list:
                        rail_id = self.trackplan_canvas.create_line(*line_coords, fill="black", width=3, tags="rail")
                        rail_ids.append(rail_id)
                    element["canvas_ids"] = rail_ids

                if element.get("_visual_hidden"):
                    self._hide_rail_visual(element)
        
                #  Sempre ocultar rails automáticos 
                is_auto_rail = (
                    element.get("auto_rail", False) or
                    element.get("rail_type") == "AUTO" or
                    (element.get("id", 0) >= 7000 and element.get("id", 0) < 8000 and 
                     element.get("parent_element") is not None)  # Só considerar auto se tiver parent_element
                )
                
                if is_auto_rail:
                    self._hide_rail_visual(element)
                
        elif element["type"] == "switch":
            # Redesenhar switch direto (type == "switch")
            image_key = f"switch_{element['angle']}_{element['mirror']}"
            if hasattr(self, 'element_images') and image_key in self.element_images:
                # Usar imagem personalizada
                main_id = self.trackplan_canvas.create_image(
                    canvas_x, canvas_y, 
                    image=self.element_images[image_key], 
                    tags="switch"
                )
                element["canvas_id"] = main_id
                element["diag_id"] = None  # Imagem já inclui diagonal
            else:
                # Usar desenho por código
                main_line, diag_line = self.get_switch_coords(canvas_x, canvas_y, element["angle"], element["mirror"])
                main_id = self.trackplan_canvas.create_line(*main_line, fill="black", width=3, tags="switch")
                diag_id = self.trackplan_canvas.create_line(*diag_line, fill="blue", width=2, tags="switch")
                element["canvas_id"] = main_id
                element["diag_id"] = diag_id
                
        elif element["type"] == "sensor":
            # Redesenhar sensor - usar formato padrão (sem direção) para imagens normais
            image_key = f"sensor_{element['angle']}"
            if hasattr(self, 'element_images') and image_key in self.element_images:
                # Usar imagem normal (sem direção)
                line_id = self.trackplan_canvas.create_image(
                    canvas_x, canvas_y, 
                    image=self.element_images[image_key], 
                    tags="sensor"
                )
                element["canvas_id"] = line_id
                element["symbol_id"] = None  # Imagem já inclui símbolo
            else:
                # Usar desenho por código
                line_coords = self.get_sensor_line_coords(canvas_x, canvas_y, element["angle"])
                symbol_coords = self.get_sensor_symbol_coords(canvas_x, canvas_y, element["angle"])
                line_id = self.trackplan_canvas.create_line(*line_coords, fill="red", width=2, tags="sensor")
                symbol_id = self.trackplan_canvas.create_oval(*symbol_coords, fill="red", outline="red", tags="sensor")
                element["canvas_id"] = line_id
                element["symbol_id"] = symbol_id
            
        elif element["type"] == "fma":
            # Redesenhar FMA - verificar se existe imagem personalizada primeiro
            # Não altera valor
            original_name = element.get("name", f"FMA{element.get('id', '')}")
            fma_angle = element.get("angle", 0)
            # Usar chave armazenada no elemento ou gerar chave padrão
            image_key = f"fma_{fma_angle}_{original_name}"
            
            if hasattr(self, 'element_images') and image_key in self.element_images:
                # Usar imagem personalizada se disponível
                fma_id = self.trackplan_canvas.create_image(
                    canvas_x, canvas_y, 
                    image=self.element_images[image_key], 
                    tags="fma"
                )
                element["canvas_id"] = fma_id
                element["box_id"] = None  # Imagem já inclui caixa
                element["text_id"] = None  # Imagem já inclui texto
            else:
                # Tentar gerar imagem novamente se não estiver no cache
                if not hasattr(self, 'element_images'):
                    self.element_images = {}
                
                custom_image = self.create_fma_image_with_integrated_text(element["angle"], element["name"])
                if custom_image:
                    self.element_images[image_key] = custom_image
                    fma_id = self.trackplan_canvas.create_image(
                        canvas_x, canvas_y, 
                        image=self.element_images[image_key], 
                        tags="fma"
                    )
                    element["canvas_id"] = fma_id
                    element["box_id"] = None
                    element["text_id"] = None
                    element["image_key"] = image_key
                else:
                    # Fallback: usar desenho por código se imagem não funcionar
                    line_coords = self.get_fma_line_coords_full(canvas_x, canvas_y, element["angle"])
                    line_id = self.trackplan_canvas.create_line(*line_coords, fill="black", width=4, tags="fma")
                    
                    box_coords = self.get_fma_box_coords_by_angle(canvas_x, canvas_y, element["angle"], element["name"])
                    box_id = self.trackplan_canvas.create_rectangle(*box_coords, 
                        fill="white", outline="black", width=1, tags="fma")
                    
                    text_x, text_y = self.get_fma_text_position_in_box(box_coords)
                    text_id = self.trackplan_canvas.create_text(
                        text_x, text_y,
                        text=element["name"],
                        font=("Arial", 6, "bold"),
                        fill="black",
                        anchor="center",
                        tags="fma"
                    )
            
                    element["canvas_id"] = line_id  # Com linha
                    element["box_id"] = box_id
                    element["text_id"] = text_id
        elif element["type"] == 'link':
            image_key = f"link_{element['angle']}"
            if hasattr(self, 'element_images') and image_key in self.element_images:
                link_id = self.trackplan_canvas.create_image(
                    canvas_x, canvas_y,
                    image=self.element_images[image_key],
                    tags="links"
                )
                element['canvas_id'] = link_id
                element['symbol_id'] = None
            else:
                # Fallback: desenha uma seta azul
                link_id = self.trackplan_canvas.create_line(
                    canvas_x - 10, canvas_y, canvas_x + 10, canvas_y,
                    arrow=tk.LAST, fill="blue", width=3, tags="link"
                )
                element['canvas_id'] = link_id
                element['symbol_id'] = None
        elif element["type"] == "crossing":
            # Tentar imagem crossing_{angle}; fallback: cruz com duas linhas
            angle = element.get("angle", 0)
            image_key = f"crossing_{angle}"
            if hasattr(self, 'element_images') and image_key in self.element_images:
                cid = self.trackplan_canvas.create_image(
                    canvas_x, canvas_y,
                    image=self.element_images[image_key],
                    tags=("rail", "crossing")
                )
                element["canvas_id"] = cid
                element["canvas_ids"] = None
                element["original_image_key"] = image_key
            else:
                half = self.grid_size // 2
                h_id = self.trackplan_canvas.create_line(
                    canvas_x - half, canvas_y, canvas_x + half, canvas_y,
                    fill="black", width=3, tags=("rail", "crossing")
                )
                v_id = self.trackplan_canvas.create_line(
                    canvas_x, canvas_y - half, canvas_x, canvas_y + half,
                    fill="black", width=3, tags=("rail", "crossing")
                )
                element["canvas_ids"] = [h_id, v_id]
                element["canvas_id"] = h_id
            
    
    def get_rail_line_coords(self, x, y, angle, mirror):
        """Calcula coordenadas do trilho baseado no ângulo e mirror
        Retorna uma lista de coordenadas para estruturas compostas (linha diagonal + linha reta)
        Usa o espaço completo 30x30 pixels para pixel art fidedigna
        """
        # Usar espaço completo: 30 pixels = 15 pixels de raio do centro
        half_size = self.grid_size // 2  # 15 pixels
        quarter_size = self.grid_size // 4  # 7.5 pixels (aproximadamente 8)
        
        # Baseado na imagem referencia.png, os trilhos são estruturas compostas
        if angle == 0:  # Horizontal simples (sem variação de mirror)
            coords = [[x - half_size, y, x + half_size, y]]
            
        elif angle == 45:  # Estruturas diagonais + horizontais
            if mirror == 0:  # 45/0 = "\_" (diagonal descendo + horizontal)
                coords = [
                    [x - half_size, y - quarter_size, x, y + quarter_size],  # Diagonal descendo
                    [x, y + quarter_size, x + half_size, y + quarter_size]   # Horizontal
                ]
            else:  # 45/1 = "_/" (horizontal + diagonal subindo)
                coords = [
                    [x - half_size, y + quarter_size, x, y + quarter_size],  # Horizontal
                    [x, y + quarter_size, x + half_size, y - quarter_size]   # Diagonal subindo
                ]
                
        elif angle == 90:  # Estruturas horizontais + diagonais
            if mirror == 0:  # 90/0 = "--\" (horizontal + diagonal descendo)
                coords = [
                    [x - half_size, y - quarter_size, x, y - quarter_size],  # Horizontal
                    [x, y - quarter_size, x + half_size, y + quarter_size]   # Diagonal descendo
                ]
            else:  # 90/1 = "/--" (diagonal subindo + horizontal)
                coords = [
                    [x - half_size, y + quarter_size, x, y - quarter_size],  # Diagonal subindo
                    [x, y - quarter_size, x + half_size, y - quarter_size]   # Horizontal
                ]
                
        elif angle == 180:  # Vertical simples (sem variação de mirror)
            coords = [[x, y - half_size, x, y + half_size]]
            
        elif angle == 225:  # Estruturas diagonais + verticais
            if mirror == 0:  # 225/0 = "|" + "/" (vertical + diagonal subindo)
                coords = [
                    [x, y - half_size, x, y + quarter_size],                 # Vertical
                    [x, y + quarter_size, x + half_size, y - quarter_size]   # Diagonal subindo
                ]
            else:  # 225/1 = "\" + "|" (diagonal descendo + vertical)
                coords = [
                    [x - half_size, y - quarter_size, x, y + quarter_size],  # Diagonal descendo
                    [x, y + quarter_size, x, y + half_size]                  # Vertical para baixo
                ]
                
        elif angle == 270:  # Estruturas diagonais simples
            if mirror == 0:  # 270/0 = "/" (diagonal subindo)
                coords = [[x - half_size, y + half_size, x + half_size, y - half_size]]
            else:  # 270/1 = "\" (diagonal descendo)
                coords = [[x - half_size, y - half_size, x + half_size, y + half_size]]
                
        elif angle == 315:  # Estruturas verticais + diagonais
            if mirror == 0:  # 315/0 = "|" + "\" (vertical + diagonal descendo)
                coords = [
                    [x, y - half_size, x, y + quarter_size],                 # Vertical
                    [x, y + quarter_size, x + half_size, y + half_size]      # Diagonal descendo
                ]
            else:  # 315/1 = "/" + "|" (diagonal subindo + vertical)
                coords = [
                    [x - half_size, y + quarter_size, x, y - quarter_size],  # Diagonal subindo
                    [x, y - quarter_size, x, y - half_size]                  # Vertical para cima
                ]
        else:
            # Padrão horizontal
            coords = [[x - half_size, y, x + half_size, y]]
        
        return coords
    
    def get_switch_coords(self, x, y, angle, mirror):
        """Calcula coordenadas do switch (linha principal + linha diagonal)
        Usa espaço completo 30x30 pixels
        """
        half_size = self.grid_size // 2  # 15 pixels
        quarter_size = self.grid_size // 4  # 7.5 pixels
        
        # Linha principal baseada no ângulo
        main_line_coords = self.get_rail_line_coords(x, y, angle, 0)  # Linha principal sempre sem mirror
        main_line = main_line_coords[0] if main_line_coords else [x - half_size, y, x + half_size, y]  # Usar primeira linha
        
        # Linha diagonal baseada no ângulo e mirror (inversão horizontal)
        if angle == 0:  # Switch horizontal para a direita
            if mirror == 0:  # Diagonal normal (para cima)
                diag_line = [x, y, x + quarter_size, y - quarter_size]
            else:  # Diagonal invertida (para baixo)
                diag_line = [x, y, x + quarter_size, y + quarter_size]
        elif angle == 45:  # Switch diagonal subindo/descendo para a direita
            if mirror == 0:
                diag_line = [x, y, x - quarter_size, y + quarter_size]
            else:
                diag_line = [x, y, x + quarter_size, y - quarter_size]
        elif angle == 90:  # Switch vertical
            if mirror == 0:  # Diagonal normal (para a direita)
                diag_line = [x, y, x + quarter_size, y + quarter_size]
            else:  # Diagonal invertida (para a esquerda)
                diag_line = [x, y, x - quarter_size, y + quarter_size]
        elif angle == 180:  # Switch horizontal para a esquerda
            if mirror == 0:  # Diagonal normal (para cima)
                diag_line = [x, y, x - quarter_size, y - quarter_size]
            else:  # Diagonal invertida (para baixo)
                diag_line = [x, y, x - quarter_size, y + quarter_size]
        elif angle == 225:  # Switch diagonal descendo/subindo para a esquerda
            if mirror == 0:
                diag_line = [x, y, x + quarter_size, y - quarter_size]
            else:
                diag_line = [x, y, x - quarter_size, y + quarter_size]
        else:
            # Padrão para outros ângulos
            if mirror == 0:
                diag_line = [x, y, x + quarter_size, y - quarter_size]
            else:
                diag_line = [x, y, x - quarter_size, y + quarter_size]
        
        return main_line, diag_line
    
    def get_sensor_line_coords(self, x, y, angle):
        """Calcula coordenadas da linha do sensor baseado no ângulo"""
        half_size = self.grid_size // 3
        
        if angle == 0:  # Horizontal
            coords = [x - half_size, y, x + half_size, y]
        elif angle == 45:  # 7:10h
            coords = [x - half_size, y + half_size, x + half_size, y - half_size]
        elif angle == 90:  # Vertical
            coords = [x, y - half_size, x, y + half_size]
        elif angle == 135:  # 10:20h
            coords = [x - half_size, y - half_size, x + half_size, y + half_size]
        elif angle == 180:  # Horizontal invertido
            coords = [x - half_size, y, x + half_size, y]
        elif angle == 225:  # 7:10h invertido
            coords = [x - half_size, y - half_size, x + half_size, y + half_size]
        elif angle == 270:  # Vertical invertido
            coords = [x, y - half_size, x, y + half_size]
        elif angle == 315:  # 10:20h invertido
            coords = [x - half_size, y + half_size, x + half_size, y - half_size]
        else:
            coords = [x - half_size, y, x + half_size, y]
        
        return coords
    
    def get_sensor_symbol_coords(self, x, y, angle):
        """Calcula coordenadas do símbolo do sensor baseado no ângulo"""
        symbol_size = 4
        offset = self.grid_size // 4
        
        # Posição do símbolo baseada no ângulo
        if angle == 0:  # Sensor acima
            symbol_x = x
            symbol_y = y - offset
        elif angle == 45:  # Sensor abaixo
            symbol_x = x + offset
            symbol_y = y + offset
        elif angle == 90:  # Sensor à direita
            symbol_x = x + offset
            symbol_y = y
        elif angle == 135:  # Sensor acima
            symbol_x = x
            symbol_y = y - offset
        elif angle == 180:  # Sensor abaixo
            symbol_x = x
            symbol_y = y + offset
        elif angle == 225:  # Sensor acima
            symbol_x = x
            symbol_y = y - offset
        elif angle == 270:  # Sensor à esquerda
            symbol_x = x - offset
            symbol_y = y
        elif angle == 315:  # Sensor abaixo
            symbol_x = x
            symbol_y = y + offset
        else:
            symbol_x = x
            symbol_y = y - offset
        
        return [symbol_x - symbol_size, symbol_y - symbol_size, 
                symbol_x + symbol_size, symbol_y + symbol_size]
    

    def delete_element_completely(self, element):
        """Deleta um elemento completamente removendo todos os seus objetos do canvas"""
        try:
            element_type = element.get('type', 'unknown')

            # remover objetos do canvas conhecidos
            if 'canvas_ids' in element and element['canvas_ids']:
                for cid in element['canvas_ids']:
                    try:
                        self.trackplan_canvas.delete(cid)
                    except Exception:
                        pass
            if 'canvas_id' in element and element['canvas_id']:
                try:
                    self.trackplan_canvas.delete(element['canvas_id'])
                except Exception:
                    pass
            if 'diag_id' in element and element['diag_id']:
                try:
                    self.trackplan_canvas.delete(element['diag_id'])
                except Exception:
                    pass
            if 'symbol_id' in element and element['symbol_id']:
                try:
                    self.trackplan_canvas.delete(element['symbol_id'])
                except Exception:
                    pass
            if 'text_id' in element and element['text_id']:
                try:
                    self.trackplan_canvas.delete(element['text_id'])
                except Exception:
                    pass
            
            #Remove associação com qualquer fma
            if element_type in ['link', 'rail', 'switch', 'sensor', 'crossing']:
                self._dissociate_element_from_all_fmas(element)

            if element_type == 'fma':
                # Remover box_id (caixa do texto)
                if 'box_id' in element and element['box_id']:
                    try:
                        self.trackplan_canvas.delete(element['box_id'])
                    except Exception as e:
                        print(f"Erro ao remover FMA box_id: {e}")
                
                # Remover text_id (texto da FMA)
                if 'text_id' in element and element['text_id']:
                    try:
                        self.trackplan_canvas.delete(element['text_id'])
                    except Exception as e:
                        print(f"Erro ao remover FMA text_id: {e}")
                
                # Limpar da cache de imagens FMA
                fma_name = element.get('name', 'FMA')
                fma_angle = element.get('angle', 0)
                cache_keys_to_remove = [
                    f"fma_{fma_angle}_{fma_name}",
                    f"fma_blue_{fma_angle}_{fma_name}",
                    element.get('image_key', '')
                ]
                
                for key in cache_keys_to_remove:
                    if key and hasattr(self, 'element_images') and key in self.element_images:
                        try:
                            del self.element_images[key]
                        except Exception:
                            pass
                            
                # Limpar cache azul se existir
                if hasattr(self, 'fma_blue_cache'):
                    blue_keys_to_remove = [k for k in self.fma_blue_cache.keys() 
                                        if f"_{fma_angle}_{fma_name}" in k]
                    for key in blue_keys_to_remove:
                        try:
                            del self.fma_blue_cache[key]
                        except Exception:
                            pass
                            
            # Remover text_id genérico (para outros elementos)
            elif 'text_id' in element and element['text_id']:
                try:
                    self.trackplan_canvas.delete(element['text_id'])
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"Erro ao deletar elemento do canvas: {e}")
            traceback.print_exc()
    
    def _dissociate_element_from_all_fmas(self, element):
        """Remove a associação do 'element' de todas as FMAs (associated_rails/sensors)."""
        try:
            etype = element.get('type')
            eid = str(element.get('id', '')).strip()
            if not eid or etype not in ('rail', 'switch', 'link', 'sensor', 'crossing'):
                return

            rails_removed = 0
            sensors_removed = 0

            for fma in getattr(self, 'trackplan_elements', []):
                if fma.get('type') != 'fma':
                    continue

                # Remover de associated_rails se for rail/switch/link/crossing
                if etype in ('rail', 'switch', 'link', 'crossing'):
                    ar = fma.get('associated_rails') or []
                    new_ar = [r for r in ar if str(r.get('refId', '')).strip() != eid]
                    if len(new_ar) != len(ar):
                        rails_removed += (len(ar) - len(new_ar))
                        fma['associated_rails'] = new_ar

                        # Atualizar listbox da FMA aberta (se for a mesma FMA)
                        if getattr(self, 'current_fma_element', None) is fma and hasattr(self, 'rails_listbox'):
                            try:
                                self.rails_listbox.delete(0, tk.END)
                                for r in new_ar:
                                    self.rails_listbox.insert(tk.END, r.get('refId', 'N/A'))
                            except Exception:
                                pass

                # Remover de associated_sensors se for sensor
                if etype == 'sensor':
                    asn = fma.get('associated_sensors') or []
                    new_asn = [s for s in asn if str(s.get('refId', '')).strip() != eid]
                    if len(new_asn) != len(asn):
                        sensors_removed += (len(asn) - len(new_asn))
                        fma['associated_sensors'] = new_asn

                        # Atualizar listbox da FMA aberta (se for a mesma FMA)
                        if getattr(self, 'current_fma_element', None) is fma and hasattr(self, 'sensors_listbox'):
                            try:
                                self.sensors_listbox.delete(0, tk.END)
                                for s in new_asn:
                                    self.sensors_listbox.insert(tk.END, f"{s.get('refId','N/A')} ({s.get('fmaPosition','center')})")
                            except Exception:
                                pass
        except Exception as e:
            print(f"Erro ao dissociar elemento das FMAs: {e}")

    def delete_element(self, element):
        """Deleta um elemento (versão original melhorada)"""
        # Verificar se é um sensor ou FMA com rail automático associado
        if element.get("type") in ["sensor", "fma"]:
            self.remove_auto_rail_when_parent_deleted(element)
        
        # Remove associação em todas as FMAS antes de excluir 
        self._dissociate_element_from_all_fmas(element)

        # Remover da lista        
        self.delete_element_completely(element)
        try:
            if element in self.trackplan_elements:
                self.trackplan_elements.remove(element)
        
            self._mark_content_changed()
        except Exception as e:
            print(f"Erro removendo elemento da lista: {e}")
    
    def on_canvas_motion(self, event):
        """Evento de movimento do mouse no canvas"""
        x = self.trackplan_canvas.canvasx(event.x)
        y = self.trackplan_canvas.canvasy(event.y)
        
        # Converter para coordenadas da grade (ajustar para espaço reservado das coordenadas)
        grid_x = int((x - self.grid_size) // self.grid_size)
        grid_y = int((y - self.grid_size) // self.grid_size)
        
        # Verificar se está dentro da grade válida
        try:
            width = int(self.width_var.get())
            height = int(self.height_var.get())
        except ValueError:
            width, height = 71, 16
        
        if 0 <= grid_x <= width and 0 <= grid_y <= height:
            coord = self.coord_to_excel(grid_x, grid_y)
            self.cell_info_var.set(f"Célula: {coord}")
        else:
            self.cell_info_var.set("Célula: ---")
    
    def save_trackplan(self):
        """Salva o trackplan em XML reutilizando generate_trackplan_xml()"""
        filename = filedialog.asksaveasfilename(
            title="Salvar Trackplan XML",
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            initialfile="Trackplan.xml"
        )
        
        if filename:
            try:
                # Usar função existente para gerar XML (sem duplicação de código)
                xml_content = self.generate_trackplan_xml()
                
                # Salvar diretamente o XML já formatado
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                
                messagebox.showinfo("Sucesso", f"Trackplan XML salvo em: {filename}")
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar Trackplan XML: {str(e)}")
                print(f"Erro detalhado: {e}")
                import traceback
                traceback.print_exc()
    
    def update_generator_from_form(self):
        """Atualiza o gerador com valores do formulário"""
        # Atualizar configurações de rede
        self.current_generator.network_config.ip_net1 = self.form_fields["IpAddressNet1"].get()
        self.current_generator.network_config.mask_net1 = self.form_fields["MaskNet1"].get()
        self.current_generator.network_config.ip_net2 = self.form_fields["IpAddressNet2"].get()
        self.current_generator.network_config.mask_net2 = self.form_fields["MaskNet2"].get()
        self.current_generator.network_config.gateway_net1 = self.form_fields["GatewayAddressNet1"].get()
        self.current_generator.network_config.gateway_net2 = self.form_fields["GatewayAddressNet2"].get()
        self.current_generator.network_config.default_gateway = self.form_fields["DefaultGateway"].get()
        self.current_generator.network_config.udp_port = int(self.form_fields["UdpPortFadc"].get())
        self.current_generator.network_config.time_server1 = self.form_fields["TimeServer1"].get()
        self.current_generator.network_config.time_server2 = self.form_fields["TimeServer2"].get()

        # Atualizar configurações da estação
        self.current_generator.station_config.config_version = self.form_fields["ConfigVersion"].get()
        self.current_generator.station_config.station_name = self.form_fields["StationName"].get()
        self.current_generator.station_config.fds_name = self.form_fields["FdsName"].get()
        self.current_generator.station_config.timezone = self.form_fields["TimeZone"].get()
    
    def save_config(self):
        """Salva a configuração atual como FdsConfig.xml"""
        filename = filedialog.asksaveasfilename(
            title="Salvar FdsConfig.xml",
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            initialfile="FdsConfig.xml"
        )
        
        if filename:
            try:
                self.update_generator_from_form()
                
                # Gerar XML do FdsConfig
                fds_xml = self.current_generator.generate_fds_config_xml(self.fds_model)
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(fds_xml)
                
                messagebox.showinfo("Sucesso", f"FdsConfig.xml salvo em: {filename}")
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar FdsConfig.xml: {str(e)}")
    
    def update_xml_preview(self):
        """Atualiza o preview dos XMLs com FMAs corretas"""
        try:            
            # Verificar se os text widgets existem
            if not hasattr(self, 'fds_xml_text') or not hasattr(self, 'trackplan_xml_text'):
                print("Text widgets XML não encontrados")
                messagebox.showerror("Erro", "Interface XML não está inicializada corretamente")
                return
            
            # === GERAR FDSCONFIG.XML ===
            try:                
                # Tentar usar o gerador se disponível
                fds_xml_content = ""
                if hasattr(self, 'current_generator') and self.current_generator:
                    try:
                        self.update_generator_from_form()
                        fds_xml_content = self.current_generator.generate_fds_config_xml(self.fds_model)
                    except Exception as e:
                        fds_xml_content = self.generate_current_fds_config_xml()
                else:
                    fds_xml_content = self.generate_current_fds_config_xml()
                
                # Atualizar texto do FdsConfig
                self.fds_xml_text.delete(1.0, tk.END)
                self.fds_xml_text.insert(1.0, fds_xml_content)
                
            except Exception as e:
                print(f"Erro ao gerar FdsConfig.xml: {e}")
                self.fds_xml_text.delete(1.0, tk.END)
                self.fds_xml_text.insert(1.0, f"<!-- Erro ao gerar FdsConfig.xml: {e} -->")
            
            # === GERAR TRACKPLAN.XML ===
            try:
                trackplan_xml_content = self.generate_trackplan_xml()
                
                # Atualizar texto do Trackplan
                self.trackplan_xml_text.delete(1.0, tk.END)
                self.trackplan_xml_text.insert(1.0, trackplan_xml_content)                
            except Exception as e:
                print(f"Erro ao gerar Trackplan.xml: {e}")
                self.trackplan_xml_text.delete(1.0, tk.END)
                self.trackplan_xml_text.insert(1.0, f"<!-- Erro ao gerar Trackplan.xml: {e} -->")
                        
        except Exception as e:
            print(f"Erro geral ao atualizar preview XML: {e}")
            messagebox.showerror("Erro", f"Erro ao atualizar preview XML: {e}")

    def generate_current_fds_config_xml(self):
        """Gera XML do FdsConfig usando dados reais carregados ou campos do formulário"""
        try:
            from xml.dom import minidom
            
            # Gerar novo XML usando o gerador
            root = ET.Element("FdsConfig")
            root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
            root.set("xsi:noNamespaceSchemaLocation", "FdsConfig.xsd")
            
            # Adicionar configurações básicas do formulário
            self._add_basic_config_from_form(root)
            
            # Adicionar elementos se existirem
            elements_elem = ET.SubElement(root, "ElementList")
            self._add_elements_from_tree(elements_elem)
            
            # Converter para string formatada sem inserir espaços extras
            try:
                tree = ET.ElementTree(root)
                ET.indent(tree, space="\t")
                xml_string = ET.tostring(root, encoding='unicode')
                return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_string}'
            except Exception:
                # Fallback sem pretty-print para evitar espaços indesejados
                xml_string = ET.tostring(root, encoding='unicode')
                return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_string}'
            
        except Exception as e:
            print(f"Erro ao gerar FdsConfig.xml: {e}")
            traceback.print_exc()
            return f'<?xml version="1.0" encoding="UTF-8"?>\n<FdsConfig>\n  <!-- Erro ao gerar XML: {e} -->\n</FdsConfig>'
        
    def _add_basic_config_from_form(self, root):
        """Adiciona configurações básicas do formulário ao XML"""
        ET.SubElement(root, "ConfigVersion").text = self.form_fields.get("ConfigVersion", tk.StringVar(value="1.0")).get()
        ET.SubElement(root, "IpAddressNet1").text = self.form_fields.get("IpAddressNet1", tk.StringVar(value="192.168.1.27")).get()
        ET.SubElement(root, "MaskNet1").text = self.form_fields.get("MaskNet1", tk.StringVar(value="255.255.255.0")).get()
        ET.SubElement(root, "IpAddressNet2").text = self.form_fields.get("IpAddressNet2", tk.StringVar(value="192.168.0.12")).get()
        ET.SubElement(root, "MaskNet2").text = self.form_fields.get("MaskNet2", tk.StringVar(value="255.255.255.0")).get()
        ET.SubElement(root, "GatewayAddressNet1").text = self.form_fields.get("GatewayAddressNet1", tk.StringVar(value="192.168.1.27")).get()
        ET.SubElement(root, "GatewayAddressNet2").text = self.form_fields.get("GatewayAddressNet2", tk.StringVar(value="192.168.0.1")).get()
        if self.fds_model == "FDS102":
            ET.SubElement(root, "DefaultGateway").text = self.form_fields.get("DefaultGateway", tk.StringVar(value="Gateway2")).get()
        ET.SubElement(root, "UdpPortFadc").text = self.form_fields.get("UdpPortFadc", tk.StringVar(value="45")).get()
        ET.SubElement(root, "TimeServer1").text = self.form_fields.get("TimeServer1", tk.StringVar(value="")).get()
        ET.SubElement(root, "TimeServer2").text = self.form_fields.get("TimeServer2", tk.StringVar(value="")).get()
        ET.SubElement(root, "StationName").text = self.form_fields.get("StationName", tk.StringVar(value="AREAIS")).get()
        ET.SubElement(root, "FdsName").text = self.form_fields.get("FdsName", tk.StringVar(value="ABRIGO 20 (IAA-4)")).get()
        if self.fds_model == "FDS102":
            ET.SubElement(root, "TimeZone").text = self.form_fields.get("TimeZone", tk.StringVar(value="America/Sao_Paulo")).get()
        else:
            ET.SubElement(root, "TimeZone").text = self.form_fields.get("TimeZone", tk.StringVar(value="CET-1CEST-2,M3.5.0/02:00:00,M10.5.0/03:00:00")).get()
    
        # Tema
        if self.fds_model == "FDS102":
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

    def _add_elements_from_tree(self, elements_elem):
        """Adiciona elementos do elements_tree ao XML"""
        elements_added = 0
        if hasattr(self, 'elements_tree') and self.elements_tree:
            try:
                for child in self.elements_tree.get_children():
                    item = self.elements_tree.item(child)
                    values = item['values']
                    
                    if len(values) >= 4:  # ID, Tipo, Atribuição, TrackplanID
                        element_node = ET.SubElement(elements_elem, "Element")
                        ET.SubElement(element_node, "ElementId").text = str(values[0])
                        ET.SubElement(element_node, "ElementType").text = str(values[1])
                        ET.SubElement(element_node, "ElementAssignment").text = str(values[2])
                        ET.SubElement(element_node, "ElementTrackplanId").text = str(values[3])
                        elements_added += 1

                        if str(values[1]) == 'ComMaster' and self.fds_model == "FDS102":
                            element_node_fcom = ET.SubElement(elements_elem, "Element")
                            ET.SubElement(element_node_fcom, "ElementId").text = str(values[0])
                            ET.SubElement(element_node_fcom, "ElementType").text = "ForwardingMaster"
                            ET.SubElement(element_node_fcom, "ElementAssignment").text = str(values[2])

                        if str(values[1]) in ['TrackSection1', 'TrackSection2'] and self.fds_model == "FDS102":
                            element_node_tse = ET.SubElement(elements_elem, "Element")
                            ET.SubElement(element_node_tse, "ElementId").text = str(values[0])
                            ET.SubElement(element_node_tse, "ElementType").text = "TrackSectionExtern1" if str(values[1]) == 'TrackSection1' else "TrackSectionExtern2"
                            ET.SubElement(element_node_tse, "ElementAssignment").text = str(values[2])
                            ET.SubElement(element_node_tse, "ElementTrackplanId").text = f'5{values[0]}'
            except Exception as e:
                print(f"Erro ao obter elementos do tree: {e}")
        
        return elements_added
    
    def generate_trackplan_xml(self):
        """Gera XML do Trackplan usando XML inteligente (sem phantom rails)"""
        try:
            # Usar o IntelligentXMLGenerator com form_fields e cubicles_data
            xml_generator = IntelligentXMLGenerator(
                self.trackplan_elements, 
                self.form_fields, 
                getattr(self, 'cubicles_data', [])
            )
            
            # Gerar XML temporário
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as temp_file:
                temp_filename = temp_file.name
            
            xml_generator.generate_smart_xml(temp_filename, fds_model=self.fds_model, next_element_id=self.next_element_id)
            
            # Ler e retornar o conteúdo do XML
            with open(temp_filename, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # Limpar arquivo temporário
            import os
            os.unlink(temp_filename)
            
            if not xml_content.strip():
                print("ALERTA: XML gerado está vazio!")
                return "<!-- XML Trackplan vazio - verifique se há elementos no canvas -->"
            
            return xml_content
            
        except Exception as e:
            print(f"Erro ao gerar Trackplan XML: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def save_trackplan_xml(self):
        """Salva o Trackplan.xml"""
        if not self.checa_validacao_antes_salvar('Trackplan'):
            return

        filename = filedialog.asksaveasfilename(
            title="Salvar Trackplan.xml",
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            initialfile="Trackplan.xml"
        )
        
        if filename:
            try:
                self.update_xml_preview()  # Gerar XML atualizado
                xml_content = self.trackplan_xml_text.get(1.0, tk.END)
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                
                messagebox.showinfo("Sucesso", f"Trackplan.xml salvo em: {filename}")
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar Trackplan.xml: {str(e)}")
    
    def save_fds_config(self):
        """Salva o FdsConfig.xml"""
        # Verificar validação antes de salvar

        if not self.checa_validacao_antes_salvar('FdsConfig'):
            return

        filename = filedialog.asksaveasfilename(
            title="Salvar FdsConfig.xml",
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            initialfile="FdsConfig.xml"
        )
        
        if filename:
            try:
                # Gerar XML atualizado primeiro
                self.update_xml_preview()
                
                # Obter conteúdo do FdsConfig do text widget
                if hasattr(self, 'fds_xml_text'):
                    xml_content = self.fds_xml_text.get(1.0, tk.END).strip()
                else:
                    # Fallback: gerar diretamente se text widget não existe
                    print("Text widget não encontrado, gerando XML diretamente...")
                    if hasattr(self, 'current_generator') and self.current_generator:
                        try:
                            self.update_generator_from_form()
                            xml_content = self.current_generator.generate_fds_config_xml(self.fds_model)
                        except Exception as e:
                            print(f"Erro no gerador FDS: {e}")
                            xml_content = self.generate_current_fds_config_xml()
                    else:
                        xml_content = self.generate_current_fds_config_xml()
                
                # Verificar se o conteúdo não está vazio
                if not xml_content or xml_content.strip() == "":
                    messagebox.showerror("Erro", "Conteúdo XML vazio. Verifique se os dados foram preenchidos corretamente.")
                    return
                
                # Salvar arquivo
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                
                messagebox.showinfo("Sucesso", f"FdsConfig.xml salvo em:\n{filename}")
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao salvar FdsConfig.xml:\n{str(e)}")
                print(f"Erro ao salvar FdsConfig.xml: {e}")
    
    def generate_fadc_aeb(self):
        local = self.form_fields.get("StationName", tk.StringVar(value="AREAIS")).get()
        num_rev = self.form_fields.get("ConfigVersion", tk.StringVar(value="1.0")).get()
        text = f"""//Local: {local}
//Programador: Pedro S. Melo Croce
//Revisor: João Paulo Rocha
//Nº de Revisão: {num_rev}
//Nota:
"""
        for cubicle in self.cubicles_data:
            for _, slot in self._iter_cubicle_slots(cubicle):
                if not slot or slot.get('type') in ('EmptySlot', 'Psc', None, ''):
                    continue
                stype = slot.get('type')
                if stype == "ComMaster":
                    sid = str(slot.get("id", ""))
                    text.append(f"""[IDENTIFICATION]

ID			12:{sid}		//ID of board
CHANNEL		4:0					

[CONFIG]
CFG_TYPE_PRTCT		7:127
TYPE_PRTCT			1:1			
TYPE_PRTCT_CODE		32:0   //0 no type protection

[CONFIG]
CFG_RSR_TYPE	7:40
TYPE_PRTCT		1:0  	//0 no type protection
RSR_TYPE		2:1		//0 (no RSR-evaluation), 1 (RSR180 - default), 2 (not allowed), 3 (RSR123)
RESERVED		6:0

[CONFIG]
CFG_ZP			7:13
TYPE_PRTCT		1:0		//0 no type protection
INTERVAL		2:3		//0 (10 ms), 1 (40 ms), 2 (80 ms), 3 (160 ms - default) 
RESERVED		2:0		
SUPERVIS_COUNT	3:1		//0..7 - number of resets permitted by a supervisor section (2 - default)///////////////realizar verificação
RESERVED		1:0     
SYSTEM_COUNT	3:1		//0..7 - number of allowed system occupancies per minute in inactive status (2- default)/////////////realizar verificação
RESERVED		1:0     
PARTIAL_COUNT	3:1		//0..7 - number of partial traversings to cause a permanent occupied indication (1 - default)
RESERVED		1:0""")
                    
        verify = self.get_verify(self)
        text.append(f"""[CONFIG]
CFG_DBV			7:44
TYPE_PRTCT		1:0		//0 no type protection
DBV				2:1      //0 (not used - default), 1 (used)
RESERVED		6:0

[CONFIG]
CFG_BEHAV_TGGL		7:15    
TYPE_PRTCT			1:0      //0 no type protection
BEHAV_RESET			3:7		//0..7 (4 is default - auxiliary reset)
RESERVED			1:0
BEHAV_SIMUL			1:1		//0 or 1 (0 is default - simulation via push buttons enabled)////////// Feito para comissionamento
RESERVED			3:0

[CONFIG]
CFG_PROJECT_AEB		7:16
TYPE_PRTCT			1:0      //0 no type protection
RESERVED			4:0	
PROJECT_NUMBER		20:1		 

[PROTECTION]
COMPONENT			8:2					//board-identification (AEB)
VERSION				48:0x{verify}	//time of data generation YYYYMMDDHHMM
CRC		32:0xcd3f651d		//ConfigCRC version 1.00

VERIFY  48:0x202511171517 """)

    def generate_fadc_com(self):
        local = self.form_fields.get("StationName", tk.StringVar(value="AREAIS")).get()
        num_rev = self.form_fields.get("ConfigVersion", tk.StringVar(value="1.0")).get()
        ip = self.form_fields.get("IpAddressNet1", tk.StringVar(value="192.168.1.27")).get()
        b1,b2,b3,b4 = ip.split(".")
        ip2 = self.form_fields.get("IpAddressNet2", tk.StringVar(value="192.168.0.12")).get()
        b1_2,b2_2,b3_2,b4_2 = ip2.split(".")
        gateway = self.form_fields.get("GatewayAddressNet1", tk.StringVar(value="192.168.1.27")).get()
        g1,g2,g3,g4 = gateway.split(".")
        text = f"""//Local: {local}

//Programador: Pedro S. Melo Croce
//Revisor: João Paulo Rocha
//Nº de Revisão: {num_rev}
//Nota:
"""
        for cubicle in self.cubicles_data:
            for _, slot in self._iter_cubicle_slots(cubicle):
                if not slot or slot.get('type') in ('EmptySlot', 'Psc', None, ''):
                    continue
                stype = slot.get('type')
                if stype == "ComMaster":
                    sid = str(slot.get("id", ""))
                    text.append(f"""[IDENTIFICATION]
ID					12:{sid}		//ID of COM board

CHANNEL				4:0			//Both Channels

[CONFIG]
CFG_INTERVAL		8:14
RESERVED			6:0
INTERVAL			2:3		//3 is default - 160 ms; 0..10 ms, 1..40 ms, 2..80 ms, 3..160 ms

//---------------------------------------   
// Configuração do endereço IP da porta 1
//---------------------------------------
[CONFIG]
CFG_MY_IP_NW1		8:1		// IP Address Channel1
MY_IP_NW1_B1		8:{b1}				 
MY_IP_NW1_B2		8:{b2}
MY_IP_NW1_B3		8:{b3}
MY_IP_NW1_B4		8:{b4}


//---------------------------------------   
// Configuração do endereço IP da porta 2
//---------------------------------------
// [CONFIG]
// CFG_MY_IP_NW2		8:2		// IP Address Channel1
// MY_IP_NW2_B1		8:{b1_2}				 
// MY_IP_NW2_B2		8:{b2_2}
// MY_IP_NW2_B3		8:{b3_2}
// MY_IP_NW2_B4		8:{b4_2}

//----------------------------------------  
// Definição da máscara de subrede própria
//----------------------------------------
[CONFIG]
CFG_MY_MASK			8:5		 
RESERVED			3:0					 
MY_MASK_NW1			5:23		//Subnet mask for network 1 		 
RESERVED			3:0					 
MY_MASK_NW2			5:0		//Subnet mask for network 2 (enter 0, if not used)


//---------------------------------
// Default gateway NW1 (Ethernet 1)  
// Configurada uma 1x por rede  
//---------------------------------
[CONFIG]
CFG_DFLT_GTWY_IP    8:{g1}    // Default gateway IP address network 1
DFLT_GTWY_IP_B1		8:{g1}
DFLT_GTWY_IP_B2	    8:{g2}
DFLT_GTWY_IP_B3		8:{g3}
DFLT_GTWY_IP_B4		8:{g4}	
//---------------------------------
// Default gateway NW2 (Ethernet 2)  
// Configurada uma 1x por rede  
//---------------------------------
// [CONFIG]
// CFG_DFLT_GTWY_IP    8:19    // Default gateway IP address network 2
// DFLT_GTWY_IP_B1		8:
// DFLT_GTWY_IP_B2		8:
// DFLT_GTWY_IP_B3		8:
// DFLT_GTWY_IP_B4		8:

//----------------------------------------------------------------
// Endereço Ip de destino da rede 1 para encaminhamento interno
// Configurado até 16x (Primeira palavra 32, segunda 33... até 47)
//----------------------------------------------------------------
""")
        verify = self.get_verify(self)
        text.append(f"""//--------------------------------------------------
// Número do projeto
//--------------------------------------------------
[CONFIG]
CFG_PROJECT_COM		8:13
RESERVED			3:0
VERIFY_VERSION		1:0			//0 is default - do not check entry “VERIFY“ and “VERSION“
PROJECT_NUMBER		20:1			//0 is default 

// PROTECTION
[PROTECTION]
COMPONENT			8:108		//identification of component, COM-Fse R2
VERSION				48:0x{verify}		//time of data generation	(YYYYMMDDhhmm)
CRC		32:0x1e9dfcf5		//ConfigCRC version 1.00

VERIFY  48:""")

    def get_verify(self):
        now = datetime.now()

        # Formata para 'yyyymmddhhmmss'
        formatted_time = now.strftime("%Y%m%d%H%M%S")
        
        return formatted_time

    def generate_recovery_zip(self):
        """Gera o arquivo FdsRecovery.zip usando a mesma lógica do save_config"""
        if not self.checa_validacao_antes_salvar('Todos'):
            return
        filename = filedialog.asksaveasfilename(
            title="Salvar FdsRecovery.zip",
            defaultextension=".zip",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")],
            initialfile="FdsRecovery.zip"
        )
        
        if filename:
            try:
                import zipfile
                
                # Atualizar gerador com dados do formulário (mesma lógica do save_config)
                self.update_generator_from_form()
                
                # Gerar FdsConfig.xml usando o gerador atualizado (mesma lógica do save_config)
                fds_xml = self.current_generator.generate_fds_config_xml(self.fds_model)
                
                # Gerar Trackplan.xml usando a função correta (mesma do save_trackplan)
                trackplan_xml = self.generate_trackplan_xml()
                
                # Criar ZIP com os dois arquivos
                with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    zipf.writestr("FdsConfig.xml", fds_xml)
                    zipf.writestr("Trackplan.xml", trackplan_xml)
                
                messagebox.showinfo("Sucesso", f"FdsRecovery.zip gerado em: {filename}")
                
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao gerar FdsRecovery.zip: {str(e)}")
                print(f"Erro ao gerar FdsRecovery.zip: {e}")

    def persist_cubicles_order(self):
        """Persiste a ordem atual dos cubicles. Se um Trackplan.xml foi carregado, reescreve a seção <Cubicles>.
        Caso contrário, salva um sidecar JSON ao lado do executável."""
        try:
            #Garante IDs por posição antes de salvar
            self.renumber_cubicles_by_position()

            file_path = getattr(self, 'cubicles_file_path', None)
            if file_path and os.path.isfile(file_path):
                self._update_cubicles_section_in_xml(file_path)
                return

            # Fallback: salvar JSON ao lado do script/app
            sidecar = os.path.join(os.path.dirname(__file__), "cubicles_order.json")
            with open(sidecar, "w", encoding="utf-8") as f:
                json.dump(self.cubicles_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erro ao persistir ordem dos cubículos: {e}")
            try:
                messagebox.showerror('Erro', f"Falha ao salvar ordem: {e}")
            except Exception as e:
                pass

    def _update_cubicles_section_in_xml(self, file_path: str):
        """Reescreve a seção <Cubicles> no XML com a ordem atual de self.cubicles_data."""
        try:
            import xml.etree.ElementTree as ET

            tree = ET.parse(file_path)
            root = tree.getroot()

            # Encontrar ou criar seção Cubicles
            cubicles_section = root.find("Cubicles")
            if cubicles_section is None:
                cubicles_section = ET.SubElement(root, "Cubicles")

            # Limpar filhos atuais
            for child in list(cubicles_section):
                cubicles_section.remove(child)

            # Recriar Cubicles na ordem atual
            for cub in self.cubicles_data:
                cub_el = ET.SubElement(
                    cubicles_section, "Cubicle",
                    {
                        "height": str(cub.get("height", "1")),
                        "id": str(cub.get("id", "")),
                        "name": str(cub.get("name", "")),
                    }
                )
                rack = cub.get("rack", {})
                rack_el = ET.SubElement(cub_el, "Rack", {"id": str(rack.get("id", ""))})

                bp = rack.get("bp", {})
                bp_el = ET.SubElement(
                    rack_el, "Bp",
                    {
                        "id": str(bp.get("id", "")),
                        "size": str(bp.get("size", "13")),
                        "startSlot": str(bp.get("startSlot", "1")),
                    }
                )

                # Ordenar e escrever slots
                slots = bp.get("slots", {})
                for slot_num, slot in sorted(slots.items(), key=lambda x: int(x[0])):
                    stype = slot.get("type", "EmptySlot")
                    sid = str(slot.get("id", ""))
                    sslot = str(slot.get("slotId", slot_num))

                    if stype == "Psc":
                        ET.SubElement(bp_el, "Psc", {"id": sid, "slotId": sslot})
                    elif stype == "Com":
                        # Mantém atributos padrão (type, redundant) como no gerador
                        el = ET.SubElement(bp_el, "Com", {
                            "id": sid,
                            "canId": str(slot.get("canId", "")),
                            "type": "COM_FSE",
                            "redundant": "NORMAL",
                            "name": str(slot.get("name", "")),
                            "slotId": sslot
                        })
                        # Opcional: manter sem conteúdo
                        _ = el
                    elif stype == "Aeb":
                        ET.SubElement(bp_el, "Aeb", {
                            "id": sid,
                            "name": str(slot.get("name", "")),
                            "canId": str(slot.get("canId", "")),
                            "refId": str(slot.get("refId", "")),
                            "slotId": sslot
                        })
                    elif stype == "IoExb":
                        ET.SubElement(bp_el, "IoExb", {
                            "id": sid,
                            "name": "IO-EXB",
                            "refId": str(slot.get("refId", "")),
                            "slotId": sslot,
                            "fma0RefId": str(slot.get("fma0RefId", "")),
                            "fma1RefId": str(slot.get("fma1RefId", "")),
                        })
                    else:
                        ET.SubElement(bp_el, "EmptySlot", {"id": sid, "slotId": sslot})

            # Gravar arquivo (mantém XML bem-formado; pode perder identação original)
            tree.write(file_path, encoding="utf-8", xml_declaration=True)
        except Exception as e:
            print(f"Erro ao atualizar seção Cubículos no XML: {e}")
    
    def renumber_cubicles_by_position(self):
        """Garante IDs fixos pela posição na lista: 9001, 9002, ..."""
        base = 9001

        for idx, cub in enumerate(getattr(self, 'cubicles_data', [])):
            next_rack_base = (8000 + 100*idx + (72000 if idx > 9 else 0)) + 1
            cub['id'] = str(base + idx)
            cub['rack']['id'] = str(next_rack_base)
            cub['rack']['bp']['id'] = str(next_rack_base + 1)

    def validate_xml_against_embedded_xsd(self, xml_content, schema_type):
        """Valida XML contra esquema XSD dos arquivos externos"""
        try:
            # Tentar importar lxml
            try:
                from lxml import etree
            except ImportError:
                return False, "Biblioteca lxml não encontrada. Instale com: pip install lxml"
            
            # Obter caminho do XSD
            xsd_path = self.get_xsd_file_path(schema_type)
            if not xsd_path or not os.path.exists(xsd_path):
                return False, f"Arquivo XSD '{schema_type}' não encontrado em: {xsd_path}"
            
            # Carregar e processar XSD
            try:
                with open(xsd_path, 'r', encoding='utf-8') as xsd_file:
                    xsd_doc = etree.parse(xsd_file)
                    xsd = etree.XMLSchema(xsd_doc)
            except Exception as e:
                return False, f"Erro ao processar esquema XSD '{xsd_path}': {e}"
            
            # Processar XML
            try:
                xml_doc = etree.fromstring(xml_content.encode('utf-8'))
            except Exception as e:
                return False, f"Erro ao processar XML: {e}"
            
            # Validar
            if xsd.validate(xml_doc):
                return True, f"XML válido conforme esquema XSD ({os.path.basename(xsd_path)})"
            else:
                errors = []
                for error in xsd.error_log:
                    errors.append(f"  Linha {error.line}: {error.message}")
                return False, f"Erros de validação ({os.path.basename(xsd_path)}):\n" + "\n".join(errors)
                
        except Exception as e:
            return False, f"Erro durante validação: {e}"

    def get_xsd_file_path(self, schema_type):
        """Retorna caminho para o arquivo XSD (funciona em .py e .exe)."""
        schema_name = f"{schema_type.capitalize()}.xsd"

        base = _app_base_dir()

        # Procura em layouts comuns (inclui Validador\XSD e Validador\)
        possible_paths = [
            base / "Validador" / "XSD" / schema_name,
            base / "Validador" / schema_name,
            base / schema_name,
            base / "XSD" / schema_name,
            base / "schemas" / schema_name,

            # Fallbacks para quando roda a partir de subpastas no modo dev
            base.parent / "Validador" / "XSD" / schema_name,
            base.parent / "Validador" / schema_name,
        ]

        for p in possible_paths:
            if p.exists():
                return str(p)

        # fallback: devolve o “melhor palpite” para debug
        return str(possible_paths[0])

    def validate_xml(self):
        """Valida XMLs gerados contra esquemas XSD externos"""
        try:
            # Verificar se os XSDs existem
            trackplan_xsd = self.get_xsd_file_path("trackplan")
            fdsconfig_xsd = self.get_xsd_file_path("fdsconfig")
            
            missing_xsds = []
            if not os.path.exists(trackplan_xsd):
                missing_xsds.append(f"Trackplan.xsd ({trackplan_xsd})")
            if not os.path.exists(fdsconfig_xsd):
                missing_xsds.append(f"FdsConfig.xsd ({fdsconfig_xsd})")
            
            if missing_xsds:
                error_msg = "Arquivos XSD não encontrados:\n" + "\n".join(missing_xsds)
                error_msg += "\n\nPor favor, certifique-se de que os arquivos XSD estão na pasta Validador/XSD/"
                messagebox.showerror("XSD não encontrado", error_msg)
                return
            
            # Limpar área de resultados se existir
            if hasattr(self, 'validation_results'):
                self.validation_results.delete(1.0, tk.END)
            
            # Criar janela de validação se não existir
            if not hasattr(self, 'validation_window') or not self.validation_window.winfo_exists():
                self.create_validation_window()
            
            self.validation_window.deiconify()  # Mostrar janela
            self.validation_results.insert(tk.END, "   INICIANDO VALIDAÇÃO XSD...\n")
            self.validation_results.insert(tk.END, "=" * 60 + "\n")
            self.validation_results.insert(tk.END, f"FdsConfig XSD: {os.path.basename(fdsconfig_xsd)}\n")
            self.validation_results.insert(tk.END, f"Trackplan XSD: {os.path.basename(trackplan_xsd)}\n")
            self.validation_results.insert(tk.END, "=" * 60 + "\n\n")
            
            validation_count = 0
            errors_found = 0
            
            # 1. Validar FdsConfig.xml
            try:
                self.validation_results.insert(tk.END, "  VALIDANDO FDSCONFIG.XML:\n")
                self.validation_results.update()
                
                fds_xml = self.generate_current_fds_config_xml()
                if fds_xml and fds_xml.strip():
                    is_valid, message = self.validate_xml_against_embedded_xsd(fds_xml, "fdsconfig")
                    
                    if is_valid:
                        self.validation_results.insert(tk.END, f"   ✅ FdsConfig.xml: VÁLIDO\n   {message}\n")
                        self.marcar_como_validado('FdsConfig.xml', fds_xml, has_errors=False)
                    else:
                        self.validation_results.insert(tk.END, f"   ❌ FdsConfig.xml: INVÁLIDO\n{message}\n")
                        errors_found += 1
                        self.marcar_como_validado('FdsConfig.xml', fds_xml, has_errors=True)
                    validation_count += 1
                else:
                    self.validation_results.insert(tk.END, "   ⚠️ FdsConfig.xml: Vazio ou não gerado\n")
            except Exception as e:
                self.validation_results.insert(tk.END, f"   ❌ ERRO: {str(e)}\n")
                errors_found += 1
            
            self.validation_results.insert(tk.END, "\n")
            
            # 2. Validar Trackplan.xml
            try:
                self.validation_results.insert(tk.END, "  VALIDANDO TRACKPLAN.XML:\n")
                self.validation_results.update()
                
                trackplan_xml = self.generate_trackplan_xml()
                if trackplan_xml and trackplan_xml.strip():
                    is_valid, message = self.validate_xml_against_embedded_xsd(trackplan_xml, "trackplan")
                    
                    if is_valid:
                        self.validation_results.insert(tk.END, f"   ✅ Trackplan.xml: VÁLIDO\n   {message}\n")
                        self.marcar_como_validado('Trackplan.xml', trackplan_xml, has_errors=False)
                    else:
                        self.validation_results.insert(tk.END, f"   ❌ Trackplan.xml: INVÁLIDO\n{message}\n")
                        errors_found += 1
                        self.marcar_como_validado('Trackplan.xml', trackplan_xml, has_errors=True)
                    validation_count += 1
                else:
                    self.validation_results.insert(tk.END, "   ⚠️ Trackplan.xml: Vazio ou não gerado\n")
            except Exception as e:
                self.validation_results.insert(tk.END, f"   ❌ Erro ao validar Trackplan.xml: {e}\n")
                errors_found += 1
            
            # Resultado final
            self.validation_results.insert(tk.END, "\n" + "=" * 60 + "\n")
            self.validation_results.insert(tk.END, f"   RESULTADO DA VALIDAÇÃO:\n")
            self.validation_results.insert(tk.END, f"   Arquivos validados: {validation_count}\n")
            self.validation_results.insert(tk.END, f"   Erros encontrados: {errors_found}\n")
            
            if errors_found == 0 and validation_count > 0:
                self.validation_results.insert(tk.END, "   TODOS OS XMLs ESTÃO VÁLIDOS!\n")
                self.validation_results.insert(tk.END, "   Arquivos prontos para uso no sistema FDS.\n")
            elif errors_found > 0:
                self.validation_results.insert(tk.END, "   CORREÇÕES NECESSÁRIAS!\n")
                self.validation_results.insert(tk.END, "   Verifique os erros acima antes de usar os XMLs.\n")
            else:
                self.validation_results.insert(tk.END, "   NENHUM XML PARA VALIDAR\n")
                self.validation_results.insert(tk.END, "   Configure elementos antes de validar.\n")
            
            self.validation_results.see(tk.END)
            
        except Exception as e:
            error_msg = f"Erro crítico na validação: {e}"
            messagebox.showerror("Erro de Validação", error_msg)

    def calculate_content_hash(self, conteudo):
        """ Calcula o hash SHA256 do conteúdo xml para validação"""
        try:
            import hashlib
            if not conteudo:
                return None

            # Normalizar conteudo (CORRIGIDO: usar variável correta)
            normalized = conteudo.strip()
            return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        except Exception as e:
            print(f"Erro ao computar hash: {e}")
            return None

    def marcar_como_validado(self, filename, conteudo, has_errors=False):
        """Marca um arquivo como validado, registrando se há erros ou não

        Args:
            filename: Nome do arquivo (ex: 'FdsConfig.xml')
            conteudo: Conteúdo XML validado
            has_errors: True se a validação encontrou erros, False se passou
        """
        try:
            import time

            # Computar hash
            hash_conteudo = self.calculate_content_hash(conteudo)

            # Registrar estado de validação
            self.validation_state[filename] = {
                'validated': not has_errors,
                'passed': not has_errors,
                'errors': [] if not has_errors else ['Erros encontrados na validação']
            }
            
            # Registrar timestamp
            self.last_validation_time[filename] = time.time()
            
            # Registrar hash (CORRIGIDO: usar variável correta)
            self.content_hash[filename] = hash_conteudo
            
            # Resetar flag de mudanças se validação bem-sucedida
            if not has_errors:
                self.changes_since_validation = False
                                        
        except Exception as e:
            print(f"Erro ao marcar validação: {e}")

    def _mark_content_changed(self):
        """Marca que houve alterações desde a última validação"""
        try:
            self.changes_since_validation = True
            
            # Limpar estados de validação (agora estão desatualizados)
            self.validation_state.clear()
            
        except Exception as e:
            print(f"Erro ao marcar alteração: {e}")

    def checa_validacao_antes_salvar(self, tipo_salvamento):
        """Verifica estado de validação e mostra dialog antes de salvar
        
        Args:
            tipo_salvamento: 'FdsConfig', 'Trackplan', ou 'Todos'
            
        Returns:
            bool: True se pode salvar, False se deve cancelar
        """
        try:
            # Verificar se houve mudanças desde a última validação
            if self.changes_since_validation:
                # Conteúdo foi alterado desde a última validação
                return self._show_validation_warning_dialog()
            
            # Verificar validação específica por tipo de salvamento
            if tipo_salvamento == 'FdsConfig':
                fds_state = self.validation_state.get('FdsConfig.xml', {})
                fds_validated = fds_state.get('validated', False)
                fds_errors = fds_state.get('errors', [])
                
                if not fds_validated:
                    # Nunca foi validado
                    return self._show_validation_warning_dialog()
                elif fds_errors:
                    # Foi validado mas tem erros
                    return self._show_validation_error_dialog('FdsConfig.xml', fds_errors)
                else:
                    # Validado sem erros
                    return True
                    
            elif tipo_salvamento == 'Trackplan':
                trackplan_state = self.validation_state.get('Trackplan.xml', {})
                trackplan_validated = trackplan_state.get('validated', False)
                trackplan_errors = trackplan_state.get('errors', [])
                
                if not trackplan_validated:
                    # Nunca foi validado
                    return self._show_validation_warning_dialog()
                elif trackplan_errors:
                    # Foi validado mas tem erros
                    return self._show_validation_error_dialog('Trackplan.xml', trackplan_errors)
                else:
                    # Validado sem erros
                    return True
                    
            elif tipo_salvamento == 'Todos':
                fds_state = self.validation_state.get('FdsConfig.xml', {})
                trackplan_state = self.validation_state.get('Trackplan.xml', {})
                
                fds_validated = fds_state.get('validated', False)
                fds_errors = fds_state.get('errors', [])
                trackplan_validated = trackplan_state.get('validated', False)
                trackplan_errors = trackplan_state.get('errors', [])
                
                # Verificar se ambos foram validados
                if not (fds_validated and trackplan_validated):
                    return self._show_validation_warning_dialog()
                
                # Verificar se há erros em algum
                all_errors = []
                if fds_errors:
                    all_errors.append(f"FdsConfig.xml: {len(fds_errors)} erro(s)")
                if trackplan_errors:
                    all_errors.append(f"Trackplan.xml: {len(trackplan_errors)} erro(s)")
                
                if all_errors:
                    return self._show_validation_error_dialog('Ambos arquivos', all_errors)
                
                # Ambos validados sem erros
                return True
            
            # Tipo de salvamento desconhecido - permitir salvar com aviso
            print(f"AVISO: Tipo de salvamento desconhecido: {tipo_salvamento}")
            return True
            
        except Exception as e:
            print(f"Erro ao verificar validação: {e}")
            # Em caso de erro, permitir salvar (fail-safe)
            return True

    def _show_validation_error_dialog(self, arquivo, erros):
        """Mostra dialog informando que há erros de validação"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("❌ Erros de Validação Encontrados")
            dialog.geometry("550x400")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Centralizar
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - 275
            y = (dialog.winfo_screenheight() // 2) - 200
            dialog.geometry(f"550x400+{x}+{y}")
            
            # Frame principal
            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Ícone de erro
            error_label = ttk.Label(main_frame, text="❌", font=("Arial", 48))
            error_label.pack(pady=(0, 15))
            
            # Mensagem principal
            title_label = ttk.Label(main_frame, 
                                text="Erros de Validação Encontrados", 
                                font=("Arial", 14, "bold"))
            title_label.pack(pady=(0, 10))
            
            # Descrição
            desc_text = f"""O arquivo {arquivo} foi validado mas contém erros que devem ser corrigidos antes de salvar.

    Erros encontrados:"""
            
            desc_label = ttk.Label(main_frame, text=desc_text, 
                                font=("Arial", 10), justify=tk.CENTER)
            desc_label.pack(pady=(0, 10))
            
            # Lista de erros
            errors_frame = ttk.LabelFrame(main_frame, text="Detalhes dos Erros", padding="10")
            errors_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
            
            errors_text = tk.Text(errors_frame, wrap=tk.WORD, height=8, font=("Courier", 9),
                                bg="#fff0f0", relief="solid", borderwidth=1)
            errors_scrollbar = ttk.Scrollbar(errors_frame, orient="vertical", 
                                            command=errors_text.yview)
            errors_text.configure(yscrollcommand=errors_scrollbar.set)
            
            # Inserir erros
            if isinstance(erros, list):
                for erro in erros:
                    errors_text.insert(tk.END, f"• {erro}\n")
            else:
                errors_text.insert(tk.END, str(erros))
            
            errors_text.configure(state="disabled")
            errors_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            errors_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Variável para resultado
            result = {'action': None}
            
            def on_fix_errors():
                result['action'] = 'cancel'
                dialog.destroy()
            
            def on_save_anyway():
                result['action'] = 'save'
                dialog.destroy()
            
            # Botões
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)
            
            ttk.Button(button_frame, text="❌ Não Salvar (Corrigir Erros)", 
                    command=on_fix_errors).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="⚠️ Salvar Mesmo Assim", 
                    command=on_save_anyway).pack(side=tk.RIGHT, padx=5)
            
            # Aguardar resultado
            dialog.wait_window()
            
            return result['action'] == 'save'
            
        except Exception as e:
            print(f"Erro no dialog de erros de validação: {e}")
            return True  # Em caso de erro, permitir salvar

    def _show_validation_warning_dialog(self):
        """Mostra dialog informando que arquivos não foram validados"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Validação Recomendada")
            dialog.geometry("500x300")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Centralizar
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - 250
            y = (dialog.winfo_screenheight() // 2) - 150
            dialog.geometry(f"500x300+{x}+{y}")
            
            # Frame principal
            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Ícone de aviso
            warning_label = ttk.Label(main_frame, text="⚠️", font=("Arial", 48))
            warning_label.pack(pady=(0, 15))
            
            # Mensagem principal
            title_label = ttk.Label(main_frame, 
                                text="Arquivos Não Validados", 
                                font=("Arial", 14, "bold"))
            title_label.pack(pady=(0, 10))
            
            # Descrição
            desc_text = """Os arquivos XML não foram validados recentemente ou 
    foram alterados desde a última validação.

    Recomenda-se validar os arquivos antes de salvar 
    para garantir que estão corretos."""
            
            desc_label = ttk.Label(main_frame, text=desc_text, 
                                font=("Arial", 10), justify=tk.CENTER)
            desc_label.pack(pady=(0, 20))
            
            # Variável para resultado
            result = {'action': None}
            
            def on_validate_now():
                result['action'] = 'validate'
                dialog.destroy()
            
            def on_save_anyway():
                result['action'] = 'save'
                dialog.destroy()
            
            def on_cancel():
                result['action'] = 'cancel'
                dialog.destroy()
            
            # Botões
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)
            
            ttk.Button(button_frame, text="Validar Agora", 
                    command=on_validate_now).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Salvar Mesmo Assim", 
                    command=on_save_anyway).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Cancelar", 
                    command=on_cancel).pack(side=tk.RIGHT, padx=5)
            
            # Aguardar resultado
            dialog.wait_window()
            
            # Processar ação escolhida
            if result['action'] == 'validate':
                # Abrir validador
                self.validate_xml()
                return False  # Não salvar agora, usuário vai validar primeiro
            elif result['action'] == 'save':
                return True  # Prosseguir com salvamento
            else:  # cancel
                return False  # Não salvar
            
        except Exception as e:
            print(f"Erro no dialog de validação: {e}")
            return True  # Em caso de erro, permitir salvar

    def create_validation_window(self):
        """Cria janela de resultados de validação"""
        self.validation_window = tk.Toplevel(self.root)
        self.validation_window.title("Validação XSD - Praxis")
        self.validation_window.geometry("900x700")
        self.validation_window.transient(self.root)
        
        # Ícone da janela (se disponível)
        try:
            self.validation_window.iconbitmap(default="icon.ico")
        except:
            pass
        
        # Frame principal
        main_frame = ttk.Frame(self.validation_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Cabeçalho
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = ttk.Label(header_frame, text="Validação XSD dos Arquivos XML", 
                            font=('Arial', 16, 'bold'))
        title_label.pack()
        
        subtitle_label = ttk.Label(header_frame, 
                                text="Verificação de conformidade com esquemas FDS oficiais", 
                                font=('Arial', 10))
        subtitle_label.pack(pady=(5, 0))
        
        # Área de texto com scroll
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.validation_results = tk.Text(text_frame, wrap=tk.WORD, font=("Consolas", 10),
                                        bg="#f8f9fa", relief="solid", borderwidth=1)
        
        v_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.validation_results.yview)
        h_scrollbar = ttk.Scrollbar(text_frame, orient="horizontal", command=self.validation_results.xview)
        
        self.validation_results.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.validation_results.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        
        # Rodapé com botões
        footer_frame = ttk.Frame(main_frame)
        footer_frame.pack(fill=tk.X, pady=(15, 0))
        
        # Botões à esquerda
        left_buttons = ttk.Frame(footer_frame)
        left_buttons.pack(side=tk.LEFT)
        
        ttk.Button(left_buttons, text="Validar Novamente", 
                command=self.validate_xml).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(left_buttons, text="Copiar Resultados", 
                command=self.copy_validation_results).pack(side=tk.LEFT, padx=(0, 10))
        
        # Botões à direita
        right_buttons = ttk.Frame(footer_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons, text="Localizar XSDs", 
                command=self.show_xsd_locations).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(right_buttons, text="Fechar", 
                command=self.validation_window.withdraw).pack(side=tk.LEFT)

    def show_xsd_locations(self):
        """Mostra onde o sistema procura pelos arquivos XSD"""
        info = "  LOCALIZAÇÃO DOS ARQUIVOS XSD:\n\n"
        
        for schema_type in ["trackplan", "fdsconfig"]:
            info += f"   {schema_type.capitalize()}.xsd:\n"
            
            base_dir = os.path.dirname(os.path.abspath(__file__))
            possible_paths = [
                os.path.join(base_dir, "..", "Validador", "XSD", f"{schema_type.capitalize()}.xsd"),
                os.path.join(base_dir, f"{schema_type.capitalize()}.xsd"),
                os.path.join(base_dir, "..", "XSD", f"{schema_type.capitalize()}.xsd"),
                os.path.join(base_dir, "schemas", f"{schema_type.capitalize()}.xsd"),
            ]
            
            for i, path in enumerate(possible_paths, 1):
                normalized_path = os.path.normpath(path)
                exists = "✅" if os.path.exists(normalized_path) else "❌"
                info += f"   {i}. {exists} {normalized_path}\n"
            
            info += "\n"
        
        info += "Coloque os arquivos XSD na pasta 'Validador/XSD/' para melhor organização."        
        result = messagebox.askyesno("Localização dos XSDs", 
                            info + "\n\nDeseja abrir a pasta dos XSDs no Explorer?")
    
        if result:
            # Abrir pasta Validador/XSD no Explorer
            xsd_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Validador", "XSD")
            if os.path.exists(xsd_folder):
                os.startfile(xsd_folder)
        else:
            messagebox.showwarning("Pasta não encontrada","Pasta XSD não existe")

    def copy_validation_results(self):
        """Copia resultados da validação para área de transferência"""
        try:
            content = self.validation_results.get(1.0, tk.END)
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("Copiado", "Resultados copiados para área de transferência!")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao copiar: {e}")

    def save_all_files(self):
        """Salva todos os arquivos: FdsConfig.xml, Trackplan.xml e FdsRecovery.zip"""
        if not self.checa_validacao_antes_salvar('Todos'):
            return
        try:
            # Solicitar diretório de destino
            directory = filedialog.askdirectory(
                title="Selecionar pasta para salvar todos os arquivos",
                initialdir=os.path.expanduser("~/Desktop")
            )
            
            if not directory:
                return
            
            # Criar nomes dos arquivos
            fds_config_path = os.path.join(directory, "FdsConfig.xml")
            trackplan_path = os.path.join(directory, "Trackplan.xml")
            recovery_zip_path = os.path.join(directory, "FdsRecovery.zip")
            
            files_saved = []
            errors = []
            
            # 1. Salvar FdsConfig.xml
            try:
                self.update_xml_preview()

                if hasattr(self, 'fds_xml_text'):
                    fds_xml_content = self.fds_xml_text.get(1.0, tk.END).strip()
                else:
                    self.update_generator_from_form()
                    fds_xml_content = self.generate_current_fds_config_xml()
                if fds_xml_content and fds_xml_content.strip():
                    with open(fds_config_path, 'w', encoding='utf-8') as f:
                        f.write(fds_xml_content)
                    files_saved.append("✅ FdsConfig.xml")
                else:
                    errors.append("❌ FdsConfig.xml: Conteúdo vazio ou inválido")
            except Exception as e:
                errors.append(f"❌ FdsConfig.xml: {str(e)}")
            
            # 2. Salvar Trackplan.xml
            try:
                trackplan_xml_content = self.generate_trackplan_xml()
                if trackplan_xml_content and trackplan_xml_content.strip():
                    with open(trackplan_path, 'w', encoding='utf-8') as f:
                        f.write(trackplan_xml_content)
                    files_saved.append("✅ Trackplan.xml")
                else:
                    errors.append("❌ Trackplan.xml: Conteúdo vazio ou inválido")
            except Exception as e:
                errors.append(f"❌ Trackplan.xml: {str(e)}")
            
            # 3. Gerar FdsRecovery.zip (apenas se os XMLs foram salvos com sucesso)
            if len(files_saved) >= 2:
                try:
                    import zipfile
                    
                    with zipfile.ZipFile(recovery_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        # Adicionar FdsConfig.xml se existir
                        if os.path.exists(fds_config_path):
                            zipf.write(fds_config_path, "FdsConfig.xml")
                        
                        # Adicionar Trackplan.xml se existir
                        if os.path.exists(trackplan_path):
                            zipf.write(trackplan_path, "Trackplan.xml")
                    
                    files_saved.append("✅ FdsRecovery.zip")
                    
                except Exception as e:
                    errors.append(f"❌ FdsRecovery.zip: {str(e)}")
            else:
                errors.append("❌ FdsRecovery.zip: Não foi possível criar (XMLs com erro)")
            
            # Mostrar resultado
            result_message = f"  Arquivos salvos em: {directory}\n\n"
            
            if files_saved:
                result_message += "ARQUIVOS SALVOS:\n" + "\n".join(files_saved)
            
            if errors:
                result_message += "\n\nERROS ENCONTRADOS:\n" + "\n".join(errors)
            
            # Determinar tipo de mensagem
            if len(files_saved) == 3:
                messagebox.showinfo("Sucesso Completo", result_message)
            elif len(files_saved) > 0:
                messagebox.showwarning("Sucesso Parcial", result_message)
                print(f"⚠️ {len(files_saved)}/3 arquivos salvos com sucesso")
            else:
                messagebox.showerror("Erro", result_message)
            
        except Exception as e:
            error_msg = f"Erro geral ao salvar todos os arquivos: {str(e)}"
            messagebox.showerror("Erro Crítico", error_msg)
            
    def switch_xml_view_mode(self):
        """Alterna entre os diferentes modos de visualização XML"""
        try:
            # Salvar conteúdo atual
            current_fds_content = ""
            current_trackplan_content = ""
            
            if hasattr(self, 'fds_xml_text'):
                try:
                    current_fds_content = self.fds_xml_text.get(1.0, tk.END)
                except:
                    pass
            if hasattr(self, 'trackplan_xml_text'):
                try:
                    current_trackplan_content = self.trackplan_xml_text.get(1.0, tk.END)
                except:
                    pass
            
            # Limpar container
            for widget in self.xml_container.winfo_children():
                widget.destroy()
            
            mode = self.xml_view_mode.get()
            
            if mode == "tabs":
                self.create_xml_tabs_view()
            elif mode == "side_by_side":
                self.create_xml_side_by_side_view()
            elif mode == "vertical":
                self.create_xml_vertical_view()
            
            # Restaurar conteúdo
            if current_fds_content.strip():
                try:
                    self.fds_xml_text.delete(1.0, tk.END)
                    self.fds_xml_text.insert(1.0, current_fds_content)
                except:
                    pass
            if current_trackplan_content.strip():
                try:
                    self.trackplan_xml_text.delete(1.0, tk.END)
                    self.trackplan_xml_text.insert(1.0, current_trackplan_content)
                except:
                    pass
    
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao alterar visualização: {e}")

    def create_xml_side_by_side_view(self):
        """Cria visualização lado a lado (horizontal)"""
        # PanedWindow horizontal
        paned_window = ttk.PanedWindow(self.xml_container, orient='horizontal')
        paned_window.pack(fill=tk.BOTH, expand=True)
        
        # === PAINEL ESQUERDO: FDSCONFIG ===
        left_frame = ttk.Frame(paned_window)
        paned_window.add(left_frame, weight=1)
        
        # Header FdsConfig
        fds_header = ttk.Frame(left_frame)
        fds_header.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(fds_header, text="FdsConfig.xml", font=('Arial', 11, 'bold')).pack(side=tk.LEFT)
        
        fds_buttons = ttk.Frame(fds_header)
        fds_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(fds_buttons, text="📋", command=lambda: self.copy_xml_content("fds"), width=3).pack(side=tk.LEFT, padx=1)
        ttk.Button(fds_buttons, text="🔍", command=lambda: self.search_in_xml("fds"), width=3).pack(side=tk.LEFT, padx=1)
        ttk.Button(fds_buttons, text="📊", command=lambda: self.show_xml_info("fds"), width=3).pack(side=tk.LEFT, padx=1)
        
        # Container para FdsConfig
        fds_container = ttk.Frame(left_frame)
        fds_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.fds_xml_text = tk.Text(fds_container, wrap=tk.NONE, font=("Courier", 10))
        fds_scrollbar_y = ttk.Scrollbar(fds_container, orient="vertical", command=self.fds_xml_text.yview)
        fds_scrollbar_x = ttk.Scrollbar(fds_container, orient="horizontal", command=self.fds_xml_text.xview)
        
        self.fds_xml_text.configure(yscrollcommand=fds_scrollbar_y.set, xscrollcommand=fds_scrollbar_x.set)
        
        self.fds_xml_text.grid(row=0, column=0, sticky="nsew")
        fds_scrollbar_y.grid(row=0, column=1, sticky="ns")
        fds_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        fds_container.grid_rowconfigure(0, weight=1)
        fds_container.grid_columnconfigure(0, weight=1)
        
        # === PAINEL DIREITO: TRACKPLAN ===
        right_frame = ttk.Frame(paned_window)
        paned_window.add(right_frame, weight=1)
        
        # Header Trackplan
        trackplan_header = ttk.Frame(right_frame)
        trackplan_header.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(trackplan_header, text="Trackplan.xml", font=('Arial', 11, 'bold')).pack(side=tk.LEFT)
        
        trackplan_buttons = ttk.Frame(trackplan_header)
        trackplan_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(trackplan_buttons, text="📋", command=lambda: self.copy_xml_content("trackplan"), width=3).pack(side=tk.LEFT, padx=1)
        ttk.Button(trackplan_buttons, text="🔍", command=lambda: self.search_in_xml("trackplan"), width=3).pack(side=tk.LEFT, padx=1)
        ttk.Button(trackplan_buttons, text="📊", command=lambda: self.show_xml_info("trackplan"), width=3).pack(side=tk.LEFT, padx=1)
        
        # Container para Trackplan
        trackplan_container = ttk.Frame(right_frame)
        trackplan_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.trackplan_xml_text = tk.Text(trackplan_container, wrap=tk.NONE, font=("Courier", 10))
        trackplan_scrollbar_y = ttk.Scrollbar(trackplan_container, orient="vertical", command=self.trackplan_xml_text.yview)
        trackplan_scrollbar_x = ttk.Scrollbar(trackplan_container, orient="horizontal", command=self.trackplan_xml_text.xview)
        
        self.trackplan_xml_text.configure(yscrollcommand=trackplan_scrollbar_y.set, xscrollcommand=trackplan_scrollbar_x.set)
        
        self.trackplan_xml_text.grid(row=0, column=0, sticky="nsew")
        trackplan_scrollbar_y.grid(row=0, column=1, sticky="ns")
        trackplan_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        trackplan_container.grid_rowconfigure(0, weight=1)
        trackplan_container.grid_columnconfigure(0, weight=1)

    def create_xml_vertical_view(self):
        """Cria visualização vertical (um acima do outro)"""
        # PanedWindow vertical
        paned_window = ttk.PanedWindow(self.xml_container, orient='vertical')
        paned_window.pack(fill=tk.BOTH, expand=True)
        
        # === PAINEL SUPERIOR: FDSCONFIG ===
        top_frame = ttk.Frame(paned_window)
        paned_window.add(top_frame, weight=1)
        
        # Header FdsConfig
        fds_header = ttk.Frame(top_frame)
        fds_header.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(fds_header, text="FdsConfig.xml", font=('Arial', 11, 'bold')).pack(side=tk.LEFT)
        
        fds_buttons = ttk.Frame(fds_header)
        fds_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(fds_buttons, text="Copiar", command=lambda: self.copy_xml_content("fds")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(fds_buttons, text="Buscar", command=lambda: self.search_in_xml("fds")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(fds_buttons, text="Info", command=lambda: self.show_xml_info("fds")).pack(side=tk.LEFT)
        
        # Container para FdsConfig
        fds_container = ttk.Frame(top_frame)
        fds_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.fds_xml_text = tk.Text(fds_container, wrap=tk.NONE, font=("Courier", 10))
        fds_scrollbar_y = ttk.Scrollbar(fds_container, orient="vertical", command=self.fds_xml_text.yview)
        fds_scrollbar_x = ttk.Scrollbar(fds_container, orient="horizontal", command=self.fds_xml_text.xview)
        
        self.fds_xml_text.configure(yscrollcommand=fds_scrollbar_y.set, xscrollcommand=fds_scrollbar_x.set)
        
        self.fds_xml_text.grid(row=0, column=0, sticky="nsew")
        fds_scrollbar_y.grid(row=0, column=1, sticky="ns")
        fds_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        fds_container.grid_rowconfigure(0, weight=1)
        fds_container.grid_columnconfigure(0, weight=1)
        
        # === PAINEL INFERIOR: TRACKPLAN ===
        bottom_frame = ttk.Frame(paned_window)
        paned_window.add(bottom_frame, weight=1)
        
        # Header Trackplan
        trackplan_header = ttk.Frame(bottom_frame)
        trackplan_header.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(trackplan_header, text="Trackplan.xml", font=('Arial', 11, 'bold')).pack(side=tk.LEFT)
        
        trackplan_buttons = ttk.Frame(trackplan_header)
        trackplan_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(trackplan_buttons, text="Copiar", command=lambda: self.copy_xml_content("trackplan")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(trackplan_buttons, text="Buscar", command=lambda: self.search_in_xml("trackplan")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(trackplan_buttons, text="Info", command=lambda: self.show_xml_info("trackplan")).pack(side=tk.LEFT)
        
        # Container para Trackplan
        trackplan_container = ttk.Frame(bottom_frame)
        trackplan_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.trackplan_xml_text = tk.Text(trackplan_container, wrap=tk.NONE, font=("Courier", 10))
        trackplan_scrollbar_y = ttk.Scrollbar(trackplan_container, orient="vertical", command=self.trackplan_xml_text.yview)
        trackplan_scrollbar_x = ttk.Scrollbar(trackplan_container, orient="horizontal", command=self.trackplan_xml_text.xview)
        
        self.trackplan_xml_text.configure(yscrollcommand=trackplan_scrollbar_y.set, xscrollcommand=trackplan_scrollbar_x.set)
        
        self.trackplan_xml_text.grid(row=0, column=0, sticky="nsew")
        trackplan_scrollbar_y.grid(row=0, column=1, sticky="ns")
        trackplan_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        trackplan_container.grid_rowconfigure(0, weight=1)
        trackplan_container.grid_columnconfigure(0, weight=1)

    def update_xml_font(self, event=None):
        """Atualiza a fonte dos editores XML"""
        try:
            size = int(self.xml_font_size.get())
            font = ("Courier", size)
            
            if hasattr(self, 'fds_xml_text'):
                self.fds_xml_text.configure(font=font)
            if hasattr(self, 'trackplan_xml_text'):
                self.trackplan_xml_text.configure(font=font)
                
        except Exception as e:
            print(f"Erro ao atualizar fonte: {e}")

    def increase_xml_font(self):
        """Aumenta o tamanho da fonte"""
        try:
            current_size = int(self.xml_font_size.get())
            if current_size < 24:
                new_size = current_size + 1
                self.xml_font_size.set(str(new_size))
                self.update_xml_font()
        except Exception as e:
            print(f"Erro ao aumentar fonte: {e}")

    def decrease_xml_font(self):
        """Diminui o tamanho da fonte"""
        try:
            current_size = int(self.xml_font_size.get())
            if current_size > 6:
                new_size = current_size - 1
                self.xml_font_size.set(str(new_size))
                self.update_xml_font()
        except Exception as e:
            print(f"Erro ao diminuir fonte: {e}")

    def copy_xml_content(self, xml_type):
        """Copia o conteúdo do XML para a área de transferência"""
        try:
            if xml_type == "fds" and hasattr(self, 'fds_xml_text'):
                content = self.fds_xml_text.get(1.0, tk.END)
                filename = "FdsConfig.xml"
            elif xml_type == "trackplan" and hasattr(self, 'trackplan_xml_text'):
                content = self.trackplan_xml_text.get(1.0, tk.END)
                filename = "Trackplan.xml"
            else:
                messagebox.showwarning("Aviso", "Conteúdo XML não disponível")
                return
            
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("Copiado", f"Conteúdo do {filename} copiado para área de transferência!")
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao copiar XML: {e}")

    def search_in_xml(self, xml_type):
        """Abre diálogo de busca avançada no XML"""
        try:
            if xml_type == "fds" and hasattr(self, 'fds_xml_text'):
                text_widget = self.fds_xml_text
                title = "Buscar em FdsConfig.xml"
            elif xml_type == "trackplan" and hasattr(self, 'trackplan_xml_text'):
                text_widget = self.trackplan_xml_text
                title = "Buscar em Trackplan.xml"
            else:
                messagebox.showwarning("Aviso", "Editor XML não disponível")
                return

            # Criar janela de busca se não existir ou foi fechada
            if not hasattr(self, 'search_dialog') or not self.search_dialog.winfo_exists():
                self.create_advanced_search_dialog()
            
            # Atualizar contexto da busca
            self.search_context = {
                'text_widget': text_widget,
                'xml_type': xml_type,
                'title': title
            }
            
            # Atualizar título
            self.search_dialog.title(title)
            
            # Limpar busca anterior
            self.clear_search_highlights()
            
            # Focar janela e campo de busca
            self.search_dialog.deiconify()
            self.search_dialog.lift()
            self.search_entry.focus()
            self.search_entry.select_range(0, tk.END)
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir busca: {e}")

    def create_advanced_search_dialog(self):
        """Cria diálogo de busca avançada estilo VS Code"""
        self.search_dialog = tk.Toplevel(self.root)
        self.search_dialog.title("Buscar no XML")
        self.search_dialog.resizable(False, False)
        
        # Centralizar
        self.search_dialog.update_idletasks()
        x = (self.search_dialog.winfo_screenwidth() // 2) - 250
        y = (self.search_dialog.winfo_screenheight() // 2) - 100
        self.search_dialog.geometry(f"500x250+{x}+{y}")
        
        # Impedir fechamento pelo X (apenas ocultar)
        self.search_dialog.protocol("WM_DELETE_WINDOW", self.hide_search_dialog)
        
        # Frame principal
        main_frame = ttk.Frame(self.search_dialog, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # === CAMPO DE BUSCA ===
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="Buscar:", font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 10))
        
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=('Consolas', 10), width=40)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # Bind Enter para buscar
        self.search_entry.bind('<Return>', lambda e: self.find_next())
        self.search_entry.bind('<Shift-Return>', lambda e: self.find_previous())
        
        # === BOTÕES DE NAVEGAÇÃO ===
        nav_frame = ttk.Frame(search_frame)
        nav_frame.pack(side=tk.LEFT)
        
        ttk.Button(nav_frame, text="◄", width=3, command=self.find_previous).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="►", width=3, command=self.find_next).pack(side=tk.LEFT, padx=2)
        
        # === OPÇÕES DE BUSCA ===
        options_frame = ttk.LabelFrame(main_frame, text="Opções de Busca", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Primeira linha de opções
        row1 = ttk.Frame(options_frame)
        row1.pack(fill=tk.X, pady=(0, 5))
        
        self.match_case_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="Aa Match Case (Maiúsculas/Minúsculas)", 
                    variable=self.match_case_var,
                    command=self.on_search_option_change).pack(side=tk.LEFT, padx=(0, 20))
        
        self.whole_word_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="Palavra Inteira", 
                    variable=self.whole_word_var,
                    command=self.on_search_option_change).pack(side=tk.LEFT)
        
        # Segunda linha de opções
        row2 = ttk.Frame(options_frame)
        row2.pack(fill=tk.X)
        
        self.regex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text=".*  Usar Expressão Regular (Regex)", 
                    variable=self.regex_var,
                    command=self.on_search_option_change).pack(side=tk.LEFT, padx=(0, 20))
        
        self.wrap_search_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Busca Circular", 
                    variable=self.wrap_search_var).pack(side=tk.LEFT)
        
        # === INFORMAÇÕES DA BUSCA ===
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.search_info_var = tk.StringVar(value="Digite um termo para buscar")
        ttk.Label(info_frame, textvariable=self.search_info_var, 
                font=('Arial', 9), foreground='#666').pack(side=tk.LEFT)
        
        # === BOTÕES DE AÇÃO ===
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Buscar Todos", 
                command=self.highlight_all_matches).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Limpar Destaques", 
                command=self.clear_search_highlights).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Fechar", 
                command=self.hide_search_dialog).pack(side=tk.RIGHT)
        
        # Inicializar variáveis de busca
        self.search_matches = []
        self.current_match_index = -1
        self.search_context = None
        
        # Ocultar inicialmente
        self.search_dialog.withdraw()

    def on_search_option_change(self):
        """Callback quando opções de busca mudam"""
        # Re-executar busca com novas opções
        if self.search_var.get():
            self.highlight_all_matches()

    def find_next(self):
        """Encontra próxima ocorrência"""
        if not self.search_context:
            return
        
        search_term = self.search_var.get()
        if not search_term:
            return
        
        text_widget = self.search_context['text_widget']
        
        # Se ainda não buscou ou opções mudaram, fazer busca completa
        if not self.search_matches:
            self.highlight_all_matches()
            if not self.search_matches:
                return
        
        # Avançar para próximo
        self.current_match_index = (self.current_match_index + 1) % len(self.search_matches)
        
        # Destacar match atual
        self.highlight_current_match()

    def find_previous(self):
        """Encontra ocorrência anterior"""
        if not self.search_context:
            return
        
        search_term = self.search_var.get()
        if not search_term:
            return
        
        # Se ainda não buscou, fazer busca completa
        if not self.search_matches:
            self.highlight_all_matches()
            if not self.search_matches:
                return
        
        # Voltar para anterior
        self.current_match_index = (self.current_match_index - 1) % len(self.search_matches)
        
        # Destacar match atual
        self.highlight_current_match()

    def highlight_all_matches(self):
        """Busca e destaca todas as ocorrências"""
        if not self.search_context:
            return
        
        search_term = self.search_var.get()
        if not search_term:
            self.search_info_var.set("Digite um termo para buscar")
            return
        
        text_widget = self.search_context['text_widget']
        
        # Limpar destaques anteriores
        self.clear_search_highlights()
        
        # Resetar matches
        self.search_matches = []
        self.current_match_index = -1
        
        # Obter texto completo
        content = text_widget.get("1.0", tk.END)
        
        # Aplicar opções de busca
        if self.regex_var.get():
            # Busca com regex
            try:
                import re
                flags = re.IGNORECASE if not self.match_case_var.get() else 0
                
                # Adicionar \b para palavra inteira se necessário
                pattern = rf'\b{search_term}\b' if self.whole_word_var.get() else search_term
                
                matches = re.finditer(pattern, content, flags)
                
                for match in matches:
                    # Converter offset para linha.coluna
                    start_pos = self.offset_to_position(content, match.start())
                    end_pos = self.offset_to_position(content, match.end())
                    self.search_matches.append((start_pos, end_pos))
                    
            except re.error as e:
                self.search_info_var.set(f"Erro na expressão regular: {e}")
                return
        else:
            # Busca normal
            search_text = search_term if self.match_case_var.get() else search_term.lower()
            content_text = content if self.match_case_var.get() else content.lower()
            
            start_idx = 0
            while True:
                pos = content_text.find(search_text, start_idx)
                if pos == -1:
                    break
                
                # Verificar palavra inteira se necessário
                if self.whole_word_var.get():
                    # Verificar se é início de palavra (não tem letra/número antes)
                    if pos > 0 and content[pos-1].isalnum():
                        start_idx = pos + 1
                        continue
                    # Verificar se é fim de palavra (não tem letra/número depois)
                    end_pos = pos + len(search_term)
                    if end_pos < len(content) and content[end_pos].isalnum():
                        start_idx = pos + 1
                        continue
                
                # Converter offset para linha.coluna
                start_pos = self.offset_to_position(content, pos)
                end_pos = self.offset_to_position(content, pos + len(search_term))
                self.search_matches.append((start_pos, end_pos))
                
                start_idx = pos + 1
        
        # Destacar todos os matches
        for start, end in self.search_matches:
            text_widget.tag_add("search_match", start, end)
        
        # Configurar aparência do destaque
        text_widget.tag_config("search_match", background="#ffff00", foreground="#000000")
        
        # Atualizar info
        if self.search_matches:
            self.search_info_var.set(f"{len(self.search_matches)} ocorrência(s) encontrada(s)")
            self.current_match_index = 0
            self.highlight_current_match()
        else:
            self.search_info_var.set("Nenhuma ocorrência encontrada")

    def highlight_current_match(self):
        """Destaca o match atual com cor diferente"""
        if not self.search_matches or self.current_match_index < 0:
            return
        
        text_widget = self.search_context['text_widget']
        
        # Remover destaque anterior do match atual
        text_widget.tag_remove("current_match", "1.0", tk.END)
        
        # Destacar match atual
        start, end = self.search_matches[self.current_match_index]
        text_widget.tag_add("current_match", start, end)
        text_widget.tag_config("current_match", background="#ff6600", foreground="#ffffff")
        
        # Elevar prioridade da tag current_match
        text_widget.tag_raise("current_match")
        
        # Scroll para o match atual
        text_widget.see(start)
        
        # Atualizar info
        self.search_info_var.set(
            f"{self.current_match_index + 1} de {len(self.search_matches)} ocorrência(s)"
        )

    def clear_search_highlights(self):
        """Limpa todos os destaques de busca"""
        if not self.search_context:
            return
        
        text_widget = self.search_context['text_widget']
        text_widget.tag_remove("search_match", "1.0", tk.END)
        text_widget.tag_remove("current_match", "1.0", tk.END)
        
        self.search_matches = []
        self.current_match_index = -1
        self.search_info_var.set("Digite um termo para buscar")

    def offset_to_position(self, content, offset):
        """Converte offset de caractere para posição linha.coluna"""
        lines = content[:offset].split('\n')
        line = len(lines)
        col = len(lines[-1])
        return f"{line}.{col}"

    def hide_search_dialog(self):
        """Oculta janela de busca"""
        if hasattr(self, 'search_dialog'):
            self.clear_search_highlights()
            self.search_dialog.withdraw()

    def show_xml_info(self, xml_type):
        """ Mostra informações sobre estatísticas do XML """
        try:
            if xml_type == "fds":
                content = self.fds_xml_text.get(1.0, tk.END).strip()
                title = "Informações do FdsConfig.xml"
                info = self._get_fds_config_info(content)
            else:  # trackplan
                content = self.trackplan_xml_text.get(1.0, tk.END).strip()
                title = "Informações do Trackplan.xml"
                info = self._get_trackplan_info(content)
            
            # Criar janela de informações
            info_window = tk.Toplevel(self.root)
            info_window.title(f"{title}")
            info_window.geometry("500x600")
            info_window.transient(self.root)
            
            # Frame principal
            main_frame = ttk.Frame(info_window, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Título
            title_label = ttk.Label(main_frame, text=title, font=("Arial", 16, "bold"))
            title_label.pack(pady=(0, 15))
            
            # Área de texto para informações
            text_frame = ttk.Frame(main_frame)
            text_frame.pack(fill=tk.BOTH, expand=True)
            
            info_text = tk.Text(text_frame, wrap=tk.WORD, font=("Consolas", 10),
                            bg="#f8f9fa", relief="solid", borderwidth=1)
            scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=info_text.yview)
            info_text.configure(yscrollcommand=scrollbar.set)
            
            info_text.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")
            
            text_frame.grid_rowconfigure(0, weight=1)
            text_frame.grid_columnconfigure(0, weight=1)
            
            # Inserir informações
            info_text.insert(1.0, info)
            info_text.configure(state="disabled")
            
            # Botão fechar
            ttk.Button(main_frame, text="Fechar", command=info_window.destroy).pack(pady=(15, 0))
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gerar informações: {e}")

    def _get_fds_config_info(self, content):
        """Gera informações estatísticas do FdsConfig.xml com contagem de elementos"""
        if not content:
            return "Conteúdo XML vazio ou não gerado ainda."
        
        try:
            # Parse do XML
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)
            
            info_lines = []
            info_lines.append("ESTATÍSTICAS DO FDSCONFIG.XML")
            info_lines.append("=" * 50)
            info_lines.append("")
            
            # Informações básicas
            info_lines.append("CONFIGURAÇÕES BÁSICAS:")
            config_version = root.findtext("ConfigVersion", "N/A")
            station_name = root.findtext("StationName", "N/A")
            fds_name = root.findtext("FdsName", "N/A")
            
            info_lines.append(f"   • Modelo do FDS: {self.fds_model}")
            info_lines.append(f"   • Versão da Configuração: {config_version}")
            info_lines.append(f"   • Nome da Estação: {station_name}")
            info_lines.append(f"   • Nome do FDS: {fds_name}")
            info_lines.append("")
            
            # Configurações de rede
            info_lines.append("CONFIGURAÇÕES DE REDE:")
            ip1 = root.findtext("IpAddressNet1", "N/A")
            ip2 = root.findtext("IpAddressNet2", "N/A")
            mask1 = root.findtext("MaskNet1", "N/A")
            mask2 = root.findtext("MaskNet2", "N/A")
            gateway1 = root.findtext("GatewayAddressNet1", "N/A")
            gateway2 = root.findtext("GatewayAddressNet2", "N/A")
            default_gateway = root.findtext("DefaultGateway", "N/A")
            udp_port = root.findtext("UdpPortFadc", "N/A")
            time_server1 = root.findtext("TimeServer1", "N/A")
            time_server2 = root.findtext("TimeServer2", "N/A")
            
            info_lines.append(f"   • IP Rede 1: {ip1} / {mask1}")
            info_lines.append(f"   • Gateway Rede 1: {gateway1}")
            info_lines.append(f"   • IP Rede 2: {ip2} / {mask2}")
            info_lines.append(f"   • Gateway Rede 2: {gateway2}")
            info_lines.append(f"   • Gateway Padrão: {default_gateway}")
            info_lines.append(f"   • Porta UDP FADC: {udp_port}")
            info_lines.append(f"   • Servidor Tempo 1: {time_server1}")
            info_lines.append(f"   • Servidor Tempo 2: {time_server2}")
            info_lines.append("")
            
            # Contagem de elementos
            info_lines.append("CONTAGEM DE ELEMENTOS:")
            
            # Encontrar seção ElementList
            element_list = root.find("ElementList")
            if element_list is not None:
                elements = element_list.findall("Element")
                
                # Contar por tipo
                element_counts = {}
                element_details = {}
                
                for element in elements:
                    element_type = element.findtext("ElementType", "Unknown")
                    element_id = element.findtext("ElementId", "N/A")
                    element_assignment = element.findtext("ElementAssignment", "N/A")
                    
                    # Contar por tipo
                    if element_type not in element_counts:
                        element_counts[element_type] = 0
                        element_details[element_type] = []
                    
                    element_counts[element_type] += 1
                    element_details[element_type].append({
                        'id': element_id,
                        'assignment': element_assignment
                    })
                
                # Mostrar contagens
                total_elements = sum(element_counts.values())
                info_lines.append(f"   • Total de Elementos: {total_elements}")
                info_lines.append("")
                
                # Contagens específicas por tipo
                type_names = {
                    'ComMaster': 'ComMaster',
                    'Aeb': 'AEB',
                    'CountingHead': 'CountingHead (Sensores)',
                    'TrackSection1': 'TrackSection1 (FMA1)',
                    'TrackSection2': 'TrackSection2 (FMA2)'
                }
                
                for element_type, count in sorted(element_counts.items()):
                    display_name = type_names.get(element_type, element_type)
                    info_lines.append(f"   🔹 {display_name}: {count}")
                    
                    # Mostrar alguns exemplos (máximo 3)
                    examples = element_details[element_type][:3]
                    for example in examples:
                        info_lines.append(f"      - ID: {example['id']}, Nome: {example['assignment']}")
                    
                    if len(element_details[element_type]) > 3:
                        remaining = len(element_details[element_type]) - 3
                        info_lines.append(f"      ... e mais {remaining} elemento(s)")
                    
                    info_lines.append("")
                
                # Análise de IDs
                info_lines.append("ANÁLISE DE IDs:")
                all_ids = []
                for element in elements:
                    trackplan_id = element.findtext("ElementTrackplanId", "")
                    if trackplan_id:
                        all_ids.append(trackplan_id)
                
                if all_ids:
                    unique_ids = set(all_ids)
                    duplicates = len(all_ids) - len(unique_ids)
                    
                    info_lines.append(f"   • Total de IDs de Trackplan: {len(all_ids)}")
                    info_lines.append(f"   • IDs únicos: {len(unique_ids)}")
                    
                    if duplicates > 0:
                        info_lines.append(f"   IDs duplicados: {duplicates}")
                    else:
                        info_lines.append("   Todos os IDs são únicos")
                else:
                    info_lines.append("   Nenhum ID de Trackplan encontrado")
                
            else:
                info_lines.append("   Seção ElementList não encontrada")
            
            info_lines.append("")
            
            # Estatísticas do arquivo
            info_lines.append("ESTATÍSTICAS DO ARQUIVO:")
            lines = content.count('\n') + 1
            chars = len(content)
            size_kb = chars / 1024
            
            info_lines.append(f"   • Linhas de código: {lines}")
            info_lines.append(f"   • Caracteres: {chars:,}")
            info_lines.append(f"   • Tamanho aproximado: {size_kb:.2f} KB")
            
            return "\n".join(info_lines)
            
        except ET.ParseError as e:
            return f"Erro ao analisar XML: {e}\n\nVerifique se o XML está bem formado."
        except Exception as e:
            return f"Erro ao gerar estatísticas: {e}"

    def _get_trackplan_info(self, content):
        """Gera informações estatísticas do Trackplan.xml"""
        if not content:
            return "Conteúdo XML vazio ou não gerado ainda."
        
        try:
            # Parse do XML
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)
            
            info_lines = []
            info_lines.append("ESTATÍSTICAS DO TRACKPLAN.XML")
            info_lines.append("=" * 50)
            info_lines.append("")
            
            # Informações do FDS
            fds_elem = root.find("Fds")
            if fds_elem is not None:
                info_lines.append("INFORMAÇÕES DO FDS:")
                info_lines.append(f"   • Nome: {fds_elem.get('name', 'N/A')}")
                info_lines.append(f"   • IP: {fds_elem.get('ip', 'N/A')}")
                info_lines.append(f"   • Netmask: {fds_elem.get('netmask', 'N/A')}")
                info_lines.append(f"   • Versão: {fds_elem.get('version', 'N/A')}")
                info_lines.append("")
            
            # Informações do Track
            track_elem = root.find("Track")
            if track_elem is not None:
                info_lines.append("DIMENSÕES DO TRACKPLAN:")
                width = track_elem.get('width', 'N/A')
                height = track_elem.get('height', 'N/A')
                info_lines.append(f"   • Largura: {width} colunas")
                info_lines.append(f"   • Altura: {height} linhas")
                
                if width != 'N/A' and height != 'N/A':
                    try:
                        total_cells = (int(width) + 1) * (int(height) + 1)
                        info_lines.append(f"   • Total de células: {total_cells:,}")
                    except ValueError:
                        pass
                info_lines.append("")
            
            # Contagem de elementos
            info_lines.append("ELEMENTOS DO TRACKPLAN:")
            
            # Contar diferentes tipos de elementos
            rails = root.findall(".//Rail")
            sensors = root.findall(".//Sensor")
            fmas = root.findall(".//Fma")
            links = root.findall(".//Link")
            
            info_lines.append(f"   • Trilhos/Chaves: {len(rails)}")
            info_lines.append(f"   • Sensores: {len(sensors)}")
            info_lines.append(f"   • FMAs: {len(fmas)}")
            info_lines.append(f"   • Links: {len(links)}")
            
            total_elements = len(rails) + len(sensors) + len(fmas) + len(links)
            info_lines.append(f"   • Total de elementos: {total_elements}")
            info_lines.append("")
            
            # Análise de FMAs
            if fmas:
                info_lines.append("ANÁLISE DE FMAs:")
                fma1_count = 0
                fma2_count = 0
                
                for fma in fmas:
                    fma_id = fma.get('id', '')
                    if fma_id.startswith('3'):
                        fma1_count += 1
                    elif fma_id.startswith('4'):
                        fma2_count += 1
                
                info_lines.append(f"   • FMA1 (prefixo 3): {fma1_count}")
                info_lines.append(f"   • FMA2 (prefixo 4): {fma2_count}")
                info_lines.append("")
            
            # Cubículos
            cubicles = root.findall(".//Cubicle")
            if cubicles:
                info_lines.append("CUBÍCULOS:")
                info_lines.append(f"   • Total de cubículos: {len(cubicles)}")
                
                total_slots = 0
                for cubicle in cubicles:
                    bp = cubicle.find(".//Bp")
                    if bp is not None:
                        size = bp.get('size', '0')
                        try:
                            total_slots += int(size)
                        except ValueError:
                            pass
                
                info_lines.append(f"   • Total de slots: {total_slots}")
                info_lines.append("")
            
            # Estatísticas do arquivo
            info_lines.append("ESTATÍSTICAS DO ARQUIVO:")
            lines = content.count('\n') + 1
            chars = len(content)
            size_kb = chars / 1024
            
            info_lines.append(f"   • Linhas de código: {lines}")
            info_lines.append(f"   • Caracteres: {chars:,}")
            info_lines.append(f"   • Tamanho aproximado: {size_kb:.2f} KB")
            
            return "\n".join(info_lines)
            
        except ET.ParseError as e:
            return f"Erro ao analisar XML: {e}\n\nVerifique se o XML está bem formado."
        except Exception as e:
            return f"Erro ao gerar estatísticas: {e}"

    def create_xml_tabs_view(self):
        """Cria visualização em abas (modo padrão)"""
        # Notebook para XMLs
        self.xml_notebook = ttk.Notebook(self.xml_container)
        self.xml_notebook.pack(fill=tk.BOTH, expand=True)
        
        # === ABA FDSCONFIG.XML ===
        fds_frame = ttk.Frame(self.xml_notebook)
        self.xml_notebook.add(fds_frame, text="FdsConfig.xml")
        
        # Header para FdsConfig
        fds_header = ttk.Frame(fds_frame)
        fds_header.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(fds_header, text="FdsConfig.xml", font=('Arial', 11, 'bold')).pack(side=tk.LEFT)
        
        # Botões específicos para FdsConfig
        fds_buttons = ttk.Frame(fds_header)
        fds_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(fds_buttons, text="Copiar", command=lambda: self.copy_xml_content("fds")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(fds_buttons, text="Buscar", command=lambda: self.search_in_xml("fds")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(fds_buttons, text="Info", command=lambda: self.show_xml_info("fds")).pack(side=tk.LEFT)
        
        # Container para texto e scrollbars
        fds_text_container = ttk.Frame(fds_frame)
        fds_text_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.fds_xml_text = tk.Text(fds_text_container, wrap=tk.NONE, font=("Courier", 10))
        fds_scrollbar_y = ttk.Scrollbar(fds_text_container, orient="vertical", command=self.fds_xml_text.yview)
        fds_scrollbar_x = ttk.Scrollbar(fds_text_container, orient="horizontal", command=self.fds_xml_text.xview)
        
        self.fds_xml_text.configure(yscrollcommand=fds_scrollbar_y.set, xscrollcommand=fds_scrollbar_x.set)
        
        # Layout grid
        self.fds_xml_text.grid(row=0, column=0, sticky="nsew")
        fds_scrollbar_y.grid(row=0, column=1, sticky="ns")
        fds_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        fds_text_container.grid_rowconfigure(0, weight=1)
        fds_text_container.grid_columnconfigure(0, weight=1)
        
        # === ABA TRACKPLAN.XML ===
        trackplan_frame = ttk.Frame(self.xml_notebook)
        self.xml_notebook.add(trackplan_frame, text="Trackplan.xml")
        
        # Header para Trackplan
        trackplan_header = ttk.Frame(trackplan_frame)
        trackplan_header.pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Label(trackplan_header, text="Trackplan.xml", font=('Arial', 11, 'bold')).pack(side=tk.LEFT)
        
        # Botões específicos para Trackplan
        trackplan_buttons = ttk.Frame(trackplan_header)
        trackplan_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(trackplan_buttons, text="Copiar", command=lambda: self.copy_xml_content("trackplan")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(trackplan_buttons, text="Buscar", command=lambda: self.search_in_xml("trackplan")).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(trackplan_buttons, text="Info", command=lambda: self.show_xml_info("trackplan")).pack(side=tk.LEFT)
        
        # Container para texto e scrollbars
        trackplan_text_container = ttk.Frame(trackplan_frame)
        trackplan_text_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.trackplan_xml_text = tk.Text(trackplan_text_container, wrap=tk.NONE, font=("Courier", 10))
        trackplan_scrollbar_y = ttk.Scrollbar(trackplan_text_container, orient="vertical", command=self.trackplan_xml_text.yview)
        trackplan_scrollbar_x = ttk.Scrollbar(trackplan_text_container, orient="horizontal", command=self.trackplan_xml_text.xview)
        
        self.trackplan_xml_text.configure(yscrollcommand=trackplan_scrollbar_y.set, xscrollcommand=trackplan_scrollbar_x.set)
        
        # Layout grid
        self.trackplan_xml_text.grid(row=0, column=0, sticky="nsew")
        trackplan_scrollbar_y.grid(row=0, column=1, sticky="ns")
        trackplan_scrollbar_x.grid(row=1, column=0, sticky="ew")
        
        trackplan_text_container.grid_rowconfigure(0, weight=1)
        trackplan_text_container.grid_columnconfigure(0, weight=1)

    def save_cubicle_basic_config(self):
        """Salva as configurações básicas do cubicle"""
        try:
            if not hasattr(self, 'current_cubicle') or not self.current_cubicle:
                messagebox.showwarning("Aviso", "Nenhum cubicle selecionado")
                return
            
            for cubicle in self.cubicles_data:
                if self.cubicle_name_var.get() == cubicle.get('name'):
                    messagebox.showerror("Erro", f"Nome \"{self.cubicle_name_var.get()}\" já está em uso")
                    return
                
            # Atualizar dados do cubicle atual
            self.current_cubicle['id'] = self.cubicle_id_var.get()
            self.current_cubicle['name'] = self.cubicle_name_var.get()
            self.current_cubicle['height'] = self.cubicle_height_var.get()
            
            # Atualizar rack/bp e slots a partir do editor
            self._sync_current_cubicle_from_editor()
            
            # Atualizar lista
            self.update_cubicles_list()
            messagebox.showinfo("Sucesso", "Configurações básicas salvas")
            
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar configurações: {e}")
    
    def update_rack_layout(self):
        """Atualiza o layout visual do rack"""
        try:
            self.draw_rack_layout()
        except Exception as e:
            print(f"Erro ao atualizar layout do rack: {e}")
    
    def load_sample_cubicles(self):
        """Carrega cubicles de exemplo"""
        try:
            # Criar alguns cubicles de exemplo
            sample_cubicles = [
                {
                    'id': '9001',
                    'name': 'CUBICULO-EX-1',
                    'height': '1',
                    'rack': {
                        'id': '8001',
                        'bp': {
                            'id': '8002',
                            'size': '13',
                            'startSlot': '1',
                            'slots': {}
                        }
                    }
                }
            ]
            
            # Inicializar slots para o exemplo
            for i in range(1, 14):
                slot_type = 'Psc' if i == 1 else 'EmptySlot'
                sample_cubicles[0]['rack']['bp']['slots'][str(i)] = {
                    'id': f"{8001 + i + 1}",
                    'type': slot_type,
                    'slotId': str(i)
                }
            
            self.cubicles_data = sample_cubicles
            self.update_cubicles_list()
            
        except Exception as e:
            print(f"Erro ao carregar cubicles de exemplo: {e}")
            
    def _set_paned_position(self, paned_window):
        """Define a posição do separador do PanedWindow"""
        try:
            # Tentar definir posição do separador (300 pixels da esquerda)
            paned_window.sashpos(0, 300)
        except Exception as e:
            print(f"Não foi possível definir posição do separador: {e}")
            # Fallback: não fazer nada, usar posição padrão

    def load_help_structure(self):
        """Carrega a estrutura hierárquica da ajuda"""
        # Limpar árvore
        for item in self.help_tree.get_children():
            self.help_tree.delete(item)
        
        # Estrutura da ajuda (hierárquica)
        help_structure = {
            "Começando": {
                "Visão Geral": "overview",
                "Primeira Configuração": "first_setup",
            },
            "Configuração FDS": {
                "Configurações de Rede": "network_config",
                "Gerenciar Elementos": "elements_management",
                "Adicionar Elementos": {
                    "ComMaster": "add_commaster",
                    "AEB": "add_aeb", 
                    "CountingHead": "add_counting_head",
                    "TrackSections": "add_track_sections"
                }
            },
            "Designer Trackplan": {
                "Interface do Designer": "designer_interface",
                "Ferramentas": {
                    "Trilhos": "tool_rail",
                    "Links": "tool_link",
                    "Chaves": "tool_switch",
                    "Sensores": "tool_sensor",
                    "FMAs": "tool_fma",
                    "Seleção": "tool_select",
                    "Borracha": "tool_eraser"
                },
                "Atalhos de Teclado": "keyboard_shortcuts",
                "Configurar Grade": "grid_config",
                "Carregar/Salvar": "load_save_trackplan"
            },
            "Cubículos": {
                "Visão Geral dos Cubículos": "cubicles_overview",
                "Criar Cubículo": "create_cubicle",
                "Layout do Rack": "rack_layout",
                "Tipos de Componentes": {
                    "PSC": "component_psc",
                    "COM": "component_com",
                    "AEB": "component_aeb",
                    "IoExb": "component_ioexb",
                    "Slot Vazio": "component_empty"
                },
                "Validação": "cubicle_validation"
            },
            "Visualização XML": {
                "Modos de Visualização": "xml_view_modes",
                "Atualizar Preview": "xml_update_preview",
                "Salvar Arquivos": "xml_save_files",
                "Validação XSD": "xml_validation"
            },
            "Funcionalidades Avançadas": {
                "Desfazer/Refazer": "undo_redo",
                "Copiar/Colar": "copy_paste",
                "Seleção em Área": "area_selection",
                "Operações de Linha/Coluna": "row_column_ops",
                "Destacamento de Elementos": "element_highlighting"
            },
            "Referência": {
                "Elementos XML": "xml_elements_reference",
            }
        }
        
        # Carregar na TreeView
        self._load_help_items(help_structure, "")

    def _load_help_items(self, items, parent_id):
        """Carrega itens da ajuda recursivamente"""
        for title, content in items.items():
            if isinstance(content, dict):
                # É uma categoria com subcategorias
                item_id = self.help_tree.insert(parent_id, "end", text=title, open=True)
                self._load_help_items(content, item_id)
            else:
                # É um tópico final
                self.help_tree.insert(parent_id, "end", text=title, values=(content,))

    def _setup_search_placeholder(self, entry_widget, placeholder_text):
        """Implementa placeholder text manualmente para o campo de busca"""
        def on_focus_in(event):
            if self.help_search_var.get() == placeholder_text:
                self.help_search_var.set("")
                entry_widget.configure(foreground="black")
        
        def on_focus_out(event):
            if not self.help_search_var.get():
                self.help_search_var.set(placeholder_text)
                entry_widget.configure(foreground="gray")
    
        def on_text_change(*args):
            current_text = self.help_search_var.get()
            if current_text == placeholder_text:
                return  # Não processar o placeholder
            
            if hasattr(self, '_search_job'):
                self.help_window.after_cancel(self._search_job)
            
            self._search_job = self.help_window.after(300, self.filter_help_topics)

        # Configurar placeholder inicial
        self.help_search_var.set(placeholder_text)
        entry_widget.configure(foreground="gray")
        
        # Bind eventos
        entry_widget.bind('<FocusIn>', on_focus_in)
        entry_widget.bind('<FocusOut>', on_focus_out)

        self.help_search_var.trace_add('write', on_text_change)

    def filter_help_topics(self, *args):
        """Filtra tópicos da ajuda baseado na busca"""
        search_term = self.help_search_var.get().lower()
        
        # Ignorar texto do placeholder e campo vazio
        if search_term == "buscar na ajuda..." or not search_term.strip():
            # Recriar árvore quando busca está vazia
            self.load_help_structure()
            return
        
        # Filtrar baseado no termo
        for item in self.help_tree.get_children():
            self._filter_tree_item_recursive(item, search_term)

    def _show_all_tree_items(self):
        """Mostra todos os itens da árvore (usado quando busca é limpa)"""
        try:
            # Primeiro, obter todos os itens detached
            all_items = []
            
            # Função recursiva para coletar todos os itens
            def collect_all_items(item_id=""):
                if item_id:
                    all_items.append(item_id)
                
                # Obter filhos do item (incluindo detached)
                children = self.help_tree.get_children(item_id)
                for child in children:
                    collect_all_items(child)
            
            # Iniciar coleta a partir da raiz
            collect_all_items()
            
            # Reattach todos os itens detached
            for item in all_items:
                try:
                    parent = self.help_tree.parent(item)
                    if not parent:  # Item de nível superior
                        parent = ""
                    self.help_tree.reattach(item, parent, "end")
                except tk.TclError:
                    # Item já está attached ou não existe
                    continue
                    
        except Exception as e:
            print(f"Erro ao mostrar todos os itens: {e}")
            # Fallback: reconstruir árvore completamente
            self.populate_help_tree()

    def _show_tree_item_recursive(self, item_id, show):
        """Mostra/esconde item da árvore recursivamente"""
        try:
            if show:
                # Tentar reativar o item (pode falhar se já estiver visível)
                try:
                    self.help_tree.reattach(item_id, self.help_tree.parent(item_id), "end")
                except tk.TclError:
                    pass
            else:
                self.help_tree.detach(item_id)
            
            # Processar filhos
            for child in self.help_tree.get_children(item_id):
                self._show_tree_item_recursive(child, show)
        except Exception as e:
            print(f"Erro ao mostrar/esconder item da árvore: {e}")

    def _filter_tree_item_recursive(self, item_id, search_term):
        """Filtra árvore recursivamente baseado no termo de busca"""
        try:
            if not self.help_tree.exists(item_id):
                return False
            
            item_text = self.help_tree.item(item_id)["text"].lower()
            children = self.help_tree.get_children(item_id)
            
            # Verificar se este item corresponde à busca
            matches = search_term in item_text
            child_matches = False
            
            # Verificar filhos recursivamente
            for child in children:
                if self._filter_tree_item_recursive(child, search_term):
                    child_matches = True
            
            # Mostrar se corresponde ou tem filhos que correspondem
            should_show = matches or child_matches
            
            if should_show:
                try:
                    # Garantir que o item está visível
                    parent = self.help_tree.parent(item_id)
                    self.help_tree.reattach(item_id, parent, "end")
                    
                    # Se tem filhos que correspondem, expandir
                    if child_matches and not matches:
                        self.help_tree.item(item_id, open=True)
                except tk.TclError:
                    # Item já está no lugar certo
                    pass
            else:
                try:
                    self.help_tree.detach(item_id)
                except tk.TclError:
                    # Item já está desanexado
                    pass
            
            return should_show
            
        except Exception as e:
            print(f"Erro ao filtrar item da árvore: {e}")
            return False

    def on_help_topic_select(self, event=None):
        """Chamado quando um tópico da ajuda é selecionado"""
        selection = self.help_tree.selection()
        if not selection:
            return
        
        item_id = selection[0]
        item = self.help_tree.item(item_id)
        
        # Verificar se é um tópico final (tem valores)
        if item["values"]:
            topic_key = item["values"][0]
            self.show_help_content(topic_key, item["text"])
        else:
            # É uma categoria - expandir/contrair
            if self.help_tree.item(item_id, "open"):
                self.help_tree.item(item_id, open=False)
            else:
                self.help_tree.item(item_id, open=True)

    def show_help_content(self, topic_key, title):
        """Mostra o conteúdo da ajuda para o tópico selecionado"""
        # Construir breadcrumb
        breadcrumb = self._build_breadcrumb(topic_key)
        self.help_breadcrumb_var.set(breadcrumb)
        
        # Limpar conteúdo anterior
        for widget in self.help_content_frame.winfo_children():
            widget.destroy()
        
        # Carregar conteúdo específico
        content_method = f"_show_help_{topic_key}"
        if hasattr(self, content_method):
            getattr(self, content_method)()
        else:
            self._show_help_generic(topic_key, title)

    def _build_breadcrumb(self, topic_key):
        """Constrói o breadcrumb para o tópico"""
        breadcrumbs = {
            "overview": "Início > Começando > Visão Geral",
            "first_setup": "Início > Começando > Primeira Configuração",
            "network_config": "Início > Configuração FDS > Configurações de Rede",
            "elements_management": "Início > Configuração FDS > Gerenciar Elementos",
            "add_commaster": "Início > Configuração FDS > Adicionar > ComMaster",
            "add_aeb": "Início > Configuração FDS > Adicionar > AEB",
            "add_counting_head": "Início > Configuração FDS > Adicionar > CountingHead",
            "add_track_sections": "Início > Configuração FDS > Adicionar > TrackSections",
            "designer_interface": "Início > Designer Trackplan > Interface do Designer",
            "tool_rail": "Início > Designer Trackplan > Ferramentas > Trilhos",
            "tool_link": "Início > Designer Trackplan > Ferramentas > Links",
            "tool_switch": "Início > Designer Trackplan > Ferramentas > Chaves",
            "tool_sensor": "Início > Designer Trackplan > Ferramentas > Sensores",
            "tool_fma": "Início > Designer Trackplan > Ferramentas > FMAs",
            "tool_select": "Início > Designer Trackplan > Ferramentas > Seleção",
            "tool_eraser": "Início > Designer Trackplan > Ferramentas > Borracha",
            "keyboard_shortcuts": "Início > Designer Trackplan > Atalhos de Teclado",
            "grid_config": "Início > Designer Trackplan > Configurar Grade",
            "load_save_trackplan": "Início > Designer Trackplan > Carregar/Salvar",
            "cubicles_overview": "Início > Cubículos > Visão Geral",
            "create_cubicle": "Início > Cubículos > Criar Cubículo",
            "rack_layout": "Início > Cubículos > Layout do Rack",
            "component_psc": "Início > Cubículos > Componentes > PSC",
            "component_com": "Início > Cubículos > Componentes > COM",
            "component_aeb": "Início > Cubículos > Componentes > AEB",
            "component_ioexb": "Início > Cubículos > Componentes > IoExb",
            "component_empty": "Início > Cubículos > Componentes > Slot Vazio",
            "cubicle_validation": "Início > Cubículos > Validação",
            "xml_view_modes": "Início > Visualização XML > Modos de Visualização",
            "xml_update_preview": "Início > Visualização XML > Atualizar Preview",
            "xml_save_files": "Início > Visualização XML > Salvar Arquivos",
            "xml_validation": "Início > Visualização XML > Validação XSD",
            "undo_redo": "Início > Funcionalidades Avançadas > Desfazer/Refazer",
            "copy_paste": "Início > Funcionalidades Avançadas > Copiar/Colar",
            "area_selection": "Início > Funcionalidades Avançadas > Seleção em Área",
            "row_column_ops": "Início > Funcionalidades Avançadas > Operações de Linha/Coluna",
            "element_highlighting": "Início > Funcionalidades Avançadas > Destacamento de Elementos",
            "xml_elements_reference": "Início > Referência > Elementos XML",
            # Adicionar mais conforme necessário
        }
        return breadcrumbs.get(topic_key, "Início > Ajuda")

    def show_help_welcome(self):
        """Mostra a tela de boas-vindas da ajuda"""
        self.help_title_var.set("Bem-vindo ao Praxis")
        self.help_breadcrumb_var.set("Início")
        
        # Limpar conteúdo
        for widget in self.help_content_frame.winfo_children():
            widget.destroy()
        
        # Conteúdo de boas-vindas
        welcome_frame = ttk.Frame(self.help_content_frame)
        welcome_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Descrição principal
        desc_text = """O Praxis é uma ferramenta completa para configuração e design de sistemas FDS (Frauscher Diagnostic System).

Esta aplicação permite criar configurações FDS, desenhar trackplans interativos, configurar cubículos e gerar os arquivos XML necessários para a utilização do sistema.

Selecione um tópico na lista à esquerda para obter ajuda detalhada sobre cada funcionalidade ou uma aba abaixo para começar a desenvolver."""
        
        # Substitua o desc_label por:
        desc_frame = ttk.LabelFrame(welcome_frame, text="Descrição", padding="10")
        desc_frame.pack(fill=tk.X, pady=(0, 20))

        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=9, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat", cursor="arrow")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X)
        
        # Cards de início rápido
        quick_start_frame = ttk.LabelFrame(welcome_frame, text="Início Rápido", padding="15")
        quick_start_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Card 1: Configuração FDS
        card1 = self._create_help_card(quick_start_frame, 
                                    "1. Configure o FDS",
                                    "Comece preenchendo as configurações básicas de rede e estação na aba 'Configuração FDS'.",
                                    lambda: self.notebook.select(0))
        card1.pack(fill=tk.X, pady=(0, 10))
        
        # Card 2: Designer Trackplan
        card2 = self._create_help_card(quick_start_frame,
                                    "2. Desenhe o Trackplan", 
                                    "Use o Designer Trackplan para criar o layout visual dos trilhos, sensores e FMAs.",
                                    lambda: self.notebook.select(1))
        card2.pack(fill=tk.X, pady=(0, 10))
        
        # Card 3: Configurar Cubículos
        card3 = self._create_help_card(quick_start_frame,
                                    "3. Configure os Cubículos",
                                    "Configure os cubículos de hardware na aba dedicada.",
                                    lambda: self.notebook.select(2))
        card3.pack(fill=tk.X, pady=(0, 10))
        
        # Card 4: Gerar XMLs
        card4 = self._create_help_card(quick_start_frame,
                                    "4. Gere os XMLs",
                                    "Visualize e salve os arquivos XML finais na aba 'Visualização XML'.",
                                    lambda: self.notebook.select(3))
        card4.pack(fill=tk.X)

    def _create_help_card(self, parent, title, description, command=None):
        """Cria um card de ajuda estilo Microsoft"""
        card_frame = ttk.Frame(parent, relief="solid", borderwidth=1, padding="10")
        
        # Título
        title_label = ttk.Label(card_frame, text=title, font=("Arial", 12, "bold"), 
                            foreground="#0078d4")
        title_label.pack(anchor="w")
        
        # Descrição
        desc_label = ttk.Label(card_frame, text=description, font=("Arial", 10),
                            wraplength=400, justify="left")
        desc_label.pack(anchor="w", pady=(5, 0))
        
        # Botão (se comando fornecido)
        if command:
            btn_frame = ttk.Frame(card_frame)
            btn_frame.pack(anchor="w", pady=(10, 0))
            
            action_btn = ttk.Button(btn_frame, text="Ir para esta seção →", command=command)
            action_btn.pack(side=tk.LEFT)
        
        # Hover effect
        def on_enter(e):
            card_frame.configure(relief="solid", borderwidth=2)
        
        def on_leave(e):
            card_frame.configure(relief="solid", borderwidth=1)
        
        card_frame.bind("<Enter>", on_enter)
        card_frame.bind("<Leave>", on_leave)
        
        return card_frame

    # ----- MÉTODOS DE AJUDA ------- # 

    def _show_help_overview(self):
        """Mostra ajuda sobre visão geral"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título principal
        title_label = ttk.Label(content_frame, text="Visão Geral", 
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))

        # LabelFrame para as abas principais
        abas_principais_frame = ttk.LabelFrame(content_frame, text="Abas Principais", padding="10")
        abas_principais_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Introdução
        intro_text = """O Praxis é dividido nas seguintes abas principais:"""
        intro_label = ttk.Label(abas_principais_frame, text=intro_text, font=("Arial", 11))
        intro_label.pack(anchor="w", pady=(0, 15))

        # Lista de abas com descrições
        abas_info = [
            ("Configuração FDS", "Configure parâmetros de rede, estação e elementos do sistema"),
            ("Designer Trackplan", "Desenhe layouts visuais com trilhos, sensores e FMAs"),
            ("Cubículos", "Configure hardware dos cubículos e racks"),
            ("Visualização XML", "Visualize e exporte os arquivos XML finais"),
            ("Ajuda", "Esta seção de ajuda (onde você está agora)")
        ]

        for aba_nome, aba_desc in abas_info:
            # Nome da aba em negrito
            nome_label = ttk.Label(abas_principais_frame, text=f"• {aba_nome}:", 
                                font=("Arial", 11, "bold"))
            nome_label.pack(anchor="w")
            
            # Descrição indentada
            desc_label = ttk.Label(abas_principais_frame, text=aba_desc, 
                                font=("Arial", 10), wraplength=580, justify="left")
            desc_label.pack(anchor="w", padx=(20, 0))

        # Conclusão
        conclusao_text = """Cada aba possui funcionalidades específicas e trabalha em conjunto para auxiliar na configuração completa do sistema FDS."""
        conclusao_label = ttk.Label(abas_principais_frame, text=conclusao_text, 
                                font=("Arial", 11), wraplength=600, justify="left")
        conclusao_label.pack(anchor="w", pady=(15, 0))

        configfds = """• Configure parâmetros de rede do FDS (IP, Máscara, Gateway).
• Defina nomes da estação e do FDS.
• Adicione elementos e defina os IDs (sem prefixo). O sistema garante uma padronização dos IDs, adicionando automaticamente prefixos conforme necessário."""

        configfds_frame = ttk.LabelFrame(content_frame, text="Configuração FDS", padding="10")
        configfds_frame.pack(fill=tk.X)

        configfds_widget = tk.Text(configfds_frame, wrap=tk.WORD, height=4, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        configfds_widget.insert(1.0, configfds)
        configfds_widget.configure(state="disabled")
        configfds_widget.pack(fill=tk.X)


        designtrackplan = """Ferramenta de design de trackplan com interface intuitiva.
Insira trilhos, chaves, sensores e FMAs e desenvolva o seu layout.
Configure os IDs dos sensores, FMAs e outros elementos conforme necessário."""

        designtrackplan_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        designtrackplan_frame.pack(fill=tk.X)

        designtrackplan_widget = tk.Text(designtrackplan_frame, wrap=tk.WORD, height=4, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        designtrackplan_widget.insert(1.0, designtrackplan)
        designtrackplan_widget.configure(state="disabled")
        designtrackplan_widget.pack(fill=tk.X)

        cubiculos = """Configure os racks e slots físicos dos equipamentos.
Relacione placas AEB, COM e outros módulos ao trackplan.
Garante que a representação física esteja alinhada à lógica do projeto"""

        cubiculos_frame = ttk.LabelFrame(content_frame, text="Cubículos", padding="10")
        cubiculos_frame.pack(fill=tk.X)

        cubiculos_widget = tk.Text(cubiculos_frame, wrap=tk.WORD, height=4, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        cubiculos_widget.insert(1.0, cubiculos)
        cubiculos_widget.configure(state="disabled")
        cubiculos_widget.pack(fill=tk.X)

        previewxml = """Permite visualizar os arquivos FdsConfig.xml e Trackplan.xml antes da exportação.
Ferramenta de validação automática para identificar erros de IDs e referências.
Exportação rápida em formato pronto para upload no FDS. Serve apenas para visualização"""

        previewxml_frame = ttk.LabelFrame(content_frame, text="Visualização XML", padding="10")
        previewxml_frame.pack(fill=tk.X)

        previewxml_widget = tk.Text(previewxml_frame, wrap=tk.WORD, height=4, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        previewxml_widget.insert(1.0, previewxml)
        previewxml_widget.configure(state="disabled")
        previewxml_widget.pack(fill=tk.X)

        ajuda = """Explica o funcionamento das abas.
Contém dicas de boas práticas.
Central de referência para dúvidas rápidas."""

        helptab_frame = ttk.LabelFrame(content_frame, text="Ajuda", padding="10")
        helptab_frame.pack(fill=tk.X)

        ajuda_widget = tk.Text(helptab_frame, wrap=tk.WORD, height=4, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        ajuda_widget.insert(1.0, ajuda)
        ajuda_widget.configure(state="disabled")
        ajuda_widget.pack(fill=tk.X)     

        workflow = """Passo a passo ideal para usar o programa.
    1. Configure os parâmetros FDS (rede, estação e elementos).
    2. Desenhe o trackplan com trilhos, sensores e FMAs e faça as configurações dos mesmos.
    3. Configure os cubículos para alinhar hardware e software.
    4. Revise os arquivos na aba Visualização XML.
    5. Exporte os XMLs e carregue no FDS."""

        workflow_frame = ttk.LabelFrame(content_frame, text="Fluxo de Trabalho Recomendado", padding="10")
        workflow_frame.pack(fill=tk.X)

        workflow_widget = tk.Text(workflow_frame, wrap=tk.WORD, height=6, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        workflow_widget.insert(1.0, workflow)
        workflow_widget.configure(state="disabled")
        workflow_widget.pack(fill=tk.X) 

        dicas = """Sempre mantenha uma cópia de backup dos XMLs.
Evite IDs duplicados (o sistema ajuda, mas é bom revisar).
Prefira layouts claros e organizados no trackplan.
Revise as conexões físicas no campo antes de finalizar."""

        dicas_frame = ttk.LabelFrame(content_frame, text="Boas Práticas", padding="10")
        dicas_frame.pack(fill=tk.X)

        dicas_widget = tk.Text(dicas_frame, wrap=tk.WORD, height=6, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        dicas_widget.insert(1.0, dicas)
        dicas_widget.configure(state="disabled")
        dicas_widget.pack(fill=tk.X) 

    def _show_help_first_setup(self):
        """Ajuda para Primeira Configuração"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título principal
        title_label = ttk.Label(content_frame, text="Primeira Configuração", 
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))
        
        # Introdução
        intro_text = """Bem-vindo ao Praxis! Este guia vai te ajudar a configurar seu primeiro projeto FDS do zero."""
        
        intro_frame = tk.LabelFrame(content_frame, text="Descrição")
        intro_frame.pack(fill=tk.X, pady=(0, 20))

        intro_label = tk.Text(intro_frame, wrap=tk.WORD, height=2, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat", cursor="arrow")
        intro_label.insert(1.0, intro_text)
        intro_label.configure(state="disabled")
        intro_label.pack(fill=tk.X, anchor="w", padx=(15, 0))
        
        # Seção: Passo a Passo
        steps_frame = ttk.LabelFrame(content_frame, text="Passo a Passo", padding="15")
        steps_frame.pack(fill=tk.X, pady=(0, 20))
        
        steps = [
            ("1. Configuração Básica", "Vá para a aba 'Configuração FDS' e preencha as informações de rede e estação. Cadastre os elementos do sistema."),
            ("2. Desenhar Trackplan", "Use a aba 'Designer Trackplan' para criar o layout. Adicione trilhos, sensores e FMAs. Utilize as ferramentas e atalhos disponíveis."),
            ("3. Configurar Cubículos", "Configure o hardware na aba 'Cubículos'. Crie cubículos, adicione racks e slots conforme necessário."),
            ("4. Gerar XMLs", "Visualize e exporte os arquivos na aba 'Visualização XML'. Valide os XMLs antes de salvar.")
        ]
        
        for step_title, step_desc in steps:
            step_frame = ttk.Frame(steps_frame)
            step_frame.pack(fill=tk.X, pady=5)
            
            ttk.Label(step_frame, text=step_title, font=("Arial", 11, "bold")).pack(anchor="w")
            ttk.Label(step_frame, text=step_desc, font=("Arial", 10), 
                     wraplength=500).pack(anchor="w", padx=(15, 0))
        
        # Seção: Dicas Importantes
        tips_frame = ttk.LabelFrame(content_frame, text="Dicas Importantes", padding="15")
        tips_frame.pack(fill=tk.X, pady=(0, 20))
        
        tips_text = """• Salve seu trabalho frequentemente usando Ctrl+S
• Use os atalhos de teclado para agilizar o trabalho (Verifique a aba 'Atalhos do Teclado')
• Valide os XMLs antes de usar em produção
• Mantenha backups de configurações importantes"""
        
        tips_widget = tk.Text(tips_frame, wrap=tk.WORD, height=4, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        tips_widget.insert(1.0, tips_text)
        tips_widget.configure(state="disabled")
        tips_widget.pack(fill=tk.X)

    def _show_help_network_config(self):
        """Ajuda para Configurações de Rede"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título
        title_label = ttk.Label(content_frame, text="Configurações de Rede", 
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))
        
        # Descrição
        desc_text = """Configure os parâmetros de rede do sistema FDS. Essas configurações são essenciais para a comunicação entre os componentes."""
        
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()

        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=2, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))
        
        # Campos obrigatórios
        fields_frame = ttk.LabelFrame(content_frame, text="📋 Campos Obrigatórios", padding="15")
        fields_frame.pack(fill=tk.X, pady=(0, 20))
        
        fields = [
            ("IP Address Net1", "Endereço IP da entrada principal ETH1. Comumente reservada para testes e desenvolvimento"),
            ("Mask Net1", "Máscara de rede principal"),
            ("Gateway Net1", "Gateway da rede principal"),
            ("IP Address Net2", "Endereço IP da rede secundária ETH2. Reservada para implementação"),
            ("UDP Port FADC", "Porta UDP para comunicação FADC (padrão: 45)"),
            ("Time Server", "Servidores NTP para sincronização de tempo")
        ]
        
        for field_name, field_desc in fields:
            field_frame = ttk.Frame(fields_frame)
            field_frame.pack(fill=tk.X, pady=3)
            
            ttk.Label(field_frame, text=f"• {field_name}:", font=("Arial", 10, "bold")).pack(anchor="w")
            ttk.Label(field_frame, text=field_desc, font=("Arial", 9), 
                     wraplength=450).pack(anchor="w", padx=(15, 0))
        
        # Exemplos
        examples_frame = ttk.LabelFrame(content_frame, text="📝 Exemplo de Configuração", padding="15")
        examples_frame.pack(fill=tk.X)
        
        example_text = """IP Address Net1: 192.168.1.27
Mask Net1: 255.255.255.0
Gateway Net1: 192.168.1.1
IP Address Net2: 192.168.0.12
UDP Port FADC: 45
Time Server 1: 192.168.103.172"""
        
        example_widget = tk.Text(examples_frame, wrap=tk.WORD, height=6, font=("Courier", 9),
                               bg="#f8f9fa", relief="solid", borderwidth=1)
        example_widget.insert(1.0, example_text)
        example_widget.configure(state="disabled")
        example_widget.pack(fill=tk.X)

    def _show_help_elements_management(self):
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título da seção
        section_title = ttk.Label(content_frame, text="Gerenciar Elementos", 
                                font=("Arial", 16, "bold"), foreground="#0078d4")
        section_title.pack(anchor="w", pady=(0, 15))
        
        # Descrição
        desc_text = """Nesta aba você pode criar, editar e remover os elementos que compõem a configuração do FDS. 
Cada elemento corresponde a um equipamento ou função no sistema (ex.: AEB, COM, Sensores, Tracksections). 
É importante que cada elemento tenha um ID único e esteja corretamente associado ao trackplan.
Atente-se também aos prefixos que cada tipo de elemento tem. Serão explicados em suas respectivas seções de ajuda."""
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding=10)
        desc_frame.pack()

        desc_widget = tk.Text(desc_frame, wrap=tk.WORD, height=6, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_widget.insert(1.0, desc_text)
        desc_widget.configure(state="disabled")
        desc_widget.pack(fill=tk.X, pady=(0, 15))
        
        # Lista de Elementos existentes
        elements_frame = ttk.LabelFrame(content_frame, text="Lista de Elementos Existentes", padding="10")
        elements_frame.pack(fill=tk.X)
        
        elements_text = """Campos básicos:
Element Id (gerado manualmente): Id do elemento compartilhado com outros itens associados, sem prefixo. 
Tipo (AEB, COM, CountingHead, TrackSection1 e TrackSection2): Diferentes tipos de elementos presentes no sistema. Para analise individual, acesse a opção de ajuda de cada um.
Atribuição (nome): Nome gerado automaticamente a partir do elemento criado. Com exceção das TrackSections.
ID: Id do elemento que será utilizado para referências. Possui prefixo dependendo do seu tipo. Para analise individual, acesse a opção de ajuda de cada um.
Os Ids possuem os seguintes prefixo:
    0XXX = ComMaster
    1XXX = AEB
    2XXX = Sensores (ZPs)
    3XXX = Tracksection1/FMA1 (Ambos são iguais)
    4XXX = TrackSection2/FMA2 (Ambos são iguais)
    7XXX = Elementos gráficos, como trilhos.
"""

        elements_widget = tk.Text(elements_frame, wrap=tk.WORD, height=16, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        elements_widget.insert(1.0, elements_text)
        elements_widget.configure(state="disabled")
        elements_widget.pack(fill=tk.X)

        # Botões de Ação
        buttons_frame = ttk.LabelFrame(content_frame, text="Botões de Ação", padding="10")
        buttons_frame.pack(fill=tk.X)
        
        buttons_text = """➕ Adicionar novo elemento: Opção de adição de elementos a lista. Após a seleção dessa opção, um Id deverá ser cadastrado. 
➖ Remover elemento: Remove um elemento específico da lista de elementos. Escolha um elemento e selecione essa opção para fazer a exclusão do item.
Limpar Todos: Limpa todos os itens da lista de elementos permanentemente. OBS: Essa opção não limpa as configurações básicas e de rede.
"""
        buttons_widget = tk.Text(buttons_frame, wrap=tk.WORD, height=7, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        buttons_widget.insert(1.0, buttons_text)
        buttons_widget.configure(state="disabled")
        buttons_widget.pack(fill=tk.X)

        load_save_text = """Arquivos FdsConfig.xml podem ser carregados e salvos nesta mesma aba. No fim da aba, há duas opções: Salvar FdsConfig.xml e Carregar FdsConfig.xml.
Salvar FdsConfig.xml: Ao terminar a configuração, é possível salvar o arquivo FdsConfig.xml gerado. Esse arquivo pode ser carregado posteriormente ou diretamente no FDS.
Carregar FdsConfig.xml: Permite carregar um arquivo FdsConfig.xml previamente salvo. Isso é útil para continuar edições ou revisar configurações existentes.
OBS: Ao carregar um arquivo FdsConfig.xml, todos os elementos atuais serão substituídos pelos do arquivo carregado.
        """
        load_save_frame = ttk.LabelFrame(content_frame, text="Carregar/Salvar FdsConfig.xml", padding="10")
        load_save_frame.pack(fill=tk.X, anchor="w")

        load_save_widget = tk.Text(load_save_frame, wrap=tk.WORD, height=8, font=("Arial", 10),
                    bg="#f0f0f0", relief="flat")
        load_save_widget.insert(1.0, load_save_text)
        load_save_widget.configure(state="disabled")
        load_save_widget.pack(fill=tk.X)

    def _show_help_add_commaster(self):
        """Mostra ajuda sobre o elemento Comaster"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        # Título principal
        section_title = ttk.Label(content_frame, text="ComMaster (Communication Board)", 
                                font=("Arial", 16, "bold"), foreground="#0078d4")
        section_title.pack(anchor="w", pady=(0, 15))

        # Descrição
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))
        desc_text = """A ferramenta ComMaster permite gerenciar a comunicação entre os diferentes módulos do sistema. No sistema, seu Id é sempre configurado com um 0 de prefixo, não sendo necessário ser adicionado manualmente."""
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)

        howto_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="10")
        howto_frame.pack(fill=tk.X, pady=(0, 20))
        howto_text = ["1. Selecione a opção de Adicionar ComMaster",
"2. Insira o Element Id e dê OK",
"3. Verifique se o ID final está com prefixo 0 correto"]
        for step in howto_text:
            ttk.Label(howto_frame, text=step, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)

    def _show_help_add_aeb(self):
        """Mostra ajuda sobre o elemento AEB"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        # Título da seção
        section_title = ttk.Label(content_frame, text="AEB (Advanced Evaluation Board)", 
                                font=("Arial", 16, "bold"), foreground="#0078d4")
        section_title.pack(anchor="w", pady=(0, 15))

        # Descrição
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))
        desc_text = """A ferramenta AEB permite gerenciar a avaliação avançada entre os diferentes módulos do sistema. No sistema, seu Id é sempre configurado com um 1 de prefixo, não sendo necessário ser adicionado manualmente."""
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)
        
        # Como usar
        howto_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="10")
        howto_frame.pack(fill=tk.X, pady=(0, 20))
        howto_text = ['1. Selecione a opção de Adicionar AEB',
'2. Insira o Element Id e dê OK',
'3. Verifique se o Id final está com prefixo 1 correto']
        
        for step in howto_text:
            ttk.Label(howto_frame, text=step, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)

    def _show_help_add_counting_head(self):
        """Mostra ajuda sobre o elemento CountingHead"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        # Título da seção
        section_title = ttk.Label(content_frame, text="CountingHead (ZP)", 
                                font=("Arial", 16, "bold"), foreground="#0078d4")
        section_title.pack(anchor="w", pady=(0, 15))

        # Descrição
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))

        desc_text = "A ferramenta CountingHead consiste em um sensor de contagem de eixos, uma proteção de sobretensão e uma placa de avaliação. No sistema, é representado por ZP e possui um prefixo 2."
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)
      
        # Como usar
        howto_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="10")
        howto_frame.pack(fill=tk.X, pady=(0, 20))
        
        howto_text = ["1. Selecione a opção de Adicionar CountingHead",
    "2. Insira o Element Id e dê OK",
    "3. Verifique se o Id final está com prefixo 2 correto."]
        for step in howto_text:
            ttk.Label(howto_frame, text=step, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)

    def _show_help_add_track_sections(self):
        """Mostra ajuda sobre os elementos TrackSections"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        # Título da seção
        section_title = ttk.Label(content_frame, text="TrackSection (FMA)", 
                                font=("Arial", 16, "bold"), foreground="#0078d4")
        section_title.pack(anchor="w", pady=(0, 15))

        # Descrição
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))
        desc_text = """Seção numa linha entre os sistemas componentes docontadores de eixo (CountingHead). No sistema, pode ser representado também por FMA e possui um prefixo 3, para Tracksection1 (FMA1) e 4, para Tracksection2 (FMA2)."""
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)
        
        # Como usar
        howto_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="10")
        howto_frame.pack(fill=tk.X, pady=(0, 20))
        howto_text = ['1. Selecione a opção de Adicionar TrackSection',
    '2. Insira o Element Id',
    '3. Insira a Atribuição (nome) de cada TrackSection. Caso possua uma em VAGO, selecione a opção de vagar uma seção',
    '4. Verifique se o Id final está com prefixo (TrackSection1 = prefixo 3 | TrackSection2 = prefixo 4) correto.']

        for step in howto_text:
            ttk.Label(howto_frame, text=step, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)

    def _show_help_designer_interface(self):
        """Mostra ajuda sobre a interface do Designer Trackplan"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        # Título da seção
        section_title = ttk.Label(content_frame, text="Interface do Designer", 
                                font=("Arial", 16, "bold"), foreground="#0078d4")
        section_title.pack(anchor="w", pady=(0, 15))

        # Descrição
        desc_text = """O Designer é a área visual do Praxis, onde você pode montar o layout do pátio ferroviário!
Seu layout e ferramentas são inspirados na interface web do FDS, garantindo maior fidelidade e eficiência.
Aqui é possível adicionar trilhos, sensores e FMAs em uma grade organizada, representando a instalação real. 
O trackplan criado nesta aba é utilizado diretamente na configuração do FDS (Trackplan.xml)."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_widget = tk.Text(desc_frame, wrap=tk.WORD, height=6, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_widget.insert(1.0, desc_text)
        desc_widget.configure(state="disabled")
        desc_widget.pack(fill=tk.X, pady=(0, 15))

        # Designer Trackplan
        grade_text = """Representa o layout da via em formato de matriz (x,y), com opções de alteração de tamanho do grid, carregar layouts previamente desenvolvidos e salvar os projetos criados.
Trilhos, links, chaves, sensores e FMAs são posicionados com coordenadas automáticas e id provisórios. É de suma importância fazer a configuração de elementos como sensores e fmas.
Cada elemento pode ser adicionado, copiado ou apagado.

O designer possui diversos atalhos e funcionalidades, acesse o resto das opções de ajuda do Designer Trackplan para mais."""

        grade_frame = ttk.LabelFrame(content_frame, text="Área de Desenho", padding="10")
        grade_frame.pack()
        grade_widget = tk.Text(grade_frame, wrap=tk.WORD, height=9, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        grade_widget.insert(1.0, grade_text)
        grade_widget.configure(state="disabled")
        grade_widget.pack(fill=tk.X, pady=(0, 15))

    def _show_help_tool_rail(self):
        """Mostra ajuda sobre a ferramenta trilho"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        # Título da seção
        section_title = ttk.Label(content_frame, text="Trilhos",
                                font=("Arial", 16, "bold"), foreground="#0078d4")
        section_title.pack(anchor="w", pady=(0, 15))

        # Descrição
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_text = "A ferramenta Trilho permite desenhar segmentos de trilho no canvas do trackplan. Trilhos podem ter mirror e ângulos variados."
        desc_widget = tk.Text(desc_frame, wrap=tk.WORD, height=3, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_widget.insert(1.0, desc_text)
        desc_widget.configure(state="disabled")
        desc_widget.pack(fill=tk.X, pady=(0, 15))
                
        howto_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="10")
        howto_frame.pack(fill=tk.X, pady=(0, 20))
        howto_text = ["1. Selecione a ferramenta 'Trilho' na barra de ferramentas",
    "2. Escolha o ângulo desejado (0°, 45°, 90°, 180°, 225°, 270°, 315°).",
    "3. Analise o preview antes de utilizar a ferramenta",
    "4. Configure o mirror se necessário",
    "5. Clique no canvas para posicionar o trilho"]
            
        for step in howto_text:
            ttk.Label(howto_frame, text=step, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)
        
        # Atalhos
        shortcuts_frame = ttk.LabelFrame(content_frame, text="Atalhos de Teclado", padding="15")
        shortcuts_frame.pack(fill=tk.X, pady=(0, 20))
        
        shortcuts = [
            ("T", "Selecionar ferramenta Trilho"),
            ("M", "Alternar Mirror"),
            ("Mouse Wheel", "Alterar ângulo"),
            ("Delete", "Remover trilho selecionado")
        ]
        
        for key, action in shortcuts:
            shortcut_frame = ttk.Frame(shortcuts_frame)
            shortcut_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(shortcut_frame, text=f"{key}:", font=("Courier", 10, "bold"), 
                     width=15).pack(side=tk.LEFT)
            ttk.Label(shortcut_frame, text=action, font=("Arial", 10)).pack(side=tk.LEFT)
        
        # Dicas
        tips_frame = ttk.LabelFrame(content_frame, text="💡 Dicas", padding="15")
        tips_frame.pack(fill=tk.X)

        tips_text = """• Use Ctrl+Z para desfazer se colocar um trilho no lugar errado
• O mouse wheel altera o ângulo rapidamente
• Trilhos podem ser configurados por FMAs, quando ativos, ficarão em azul delimitando a FMA."""

        tips_widget = tk.Text(tips_frame, wrap=tk.WORD, height=4, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        tips_widget.insert(1.0, tips_text)
        tips_widget.configure(state="disabled")
        tips_widget.pack(fill=tk.X)

    def _show_help_tool_link(self):
        """Mostra ajuda sobre a ferramenta link"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título da seção
        section_title = ttk.Label(content_frame, text="Links",
                                font=("Arial", 16, "bold"), foreground="#0078d4")
        section_title.pack(anchor="w", pady=(0, 15))
        
        # Descrição
        desc_text = """A ferramenta Link permite desenhar setas que apontam para o próximo/anterior layout do trackplan. Links possuem URLs que devem ser completadas pelo IpAddressNet1 do trackplan a ser alcançado."""
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_widget = tk.Text(desc_frame, wrap=tk.WORD, height=3, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        desc_widget.insert(1.0, desc_text)
        desc_widget.configure(state="disabled")
        desc_widget.pack(fill=tk.X, pady=(0, 15))

        howto_frame = ttk.LabelFrame(content_frame, text="Como usar", padding="10")
        howto_frame.pack(fill=tk.X, pady=(0, 20))
        
        howto_text = ["1. Selecione a ferramenta 'Link' na barra de ferramentas",
    "2. Escolha o ângulo desejado (0°, 90°, 180° e 270°).",
    "3. Analise o preview antes de utilizar a ferramenta",
    "4. Configure o mirror se necessário",
    "5. Clique no canvas para posicionar o link"]
 
        for step in howto_text:
            ttk.Label(howto_frame, text=step, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)
        
        # Seção de dicas
        tips_frame = ttk.LabelFrame(content_frame, text="💡 Dicas", padding="10")
        tips_frame.pack(fill=tk.X)
        
        tips_text = """• Use Ctrl+Z para desfazer se colocar um link no lugar errado
• O mouse wheel altera o ângulo rapidamente
• Links podem ser selecionados nas FMAs, criando efeito de uma FMA que continua em outro layout."""
        
        tips_widget = tk.Text(tips_frame, wrap=tk.WORD, height=4, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        tips_widget.insert(1.0, tips_text)
        tips_widget.configure(state="disabled")
        tips_widget.pack(fill=tk.X)

    def _show_help_tool_switch(self):
        """Mostra ajuda sobre a ferramenta chave"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título da seção
        section_title = ttk.Label(content_frame, text="Chaves",
                                font=("Arial", 16, "bold"), foreground="#0078d4")
        section_title.pack(anchor="w", pady=(0, 15))
        
        # Descrição
        desc_text = """A ferramenta Chave permite desenhar chaves que alteram a rota de uma locomotiva. Há uma extensa variação de chaves, procure a que melhor encaixa no seu design."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_widget = tk.Text(desc_frame, wrap=tk.WORD, height=2, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        desc_widget.insert(1.0, desc_text)
        desc_widget.configure(state="disabled")
        desc_widget.pack(fill=tk.X, pady=(0, 15))

        howto_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="10")
        howto_frame.pack(fill=tk.X, pady=(0, 20))
        howto_text = ["1. Selecione a ferramenta 'Chave' na barra de ferramentas ou utilize o atalho 'C'.",
                "2. Escolha o ângulo desejado (0°, 90°, 180° e 270°).",
                "3. Analise o preview antes de utilizar a ferramenta.",
                "4. Altere o mirror se necessário.",
                "5. Clique no canvas para adicionar a chave."]
        
        for step in howto_text:
            ttk.Label(howto_frame, text=step, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)
        
        # Seção de dicas
        tips_frame = ttk.LabelFrame(content_frame, text="💡 Dicas", padding="10")
        tips_frame.pack(fill=tk.X)
        
        tips_text = """• Use Ctrl+Z para desfazer se colocar uma chave no lugar errado
• O mouse wheel altera o ângulo rapidamente
• Chaves podem ser selecionadas nas FMAs, demarcando o trajeto de uma fma.
• Use a tecla M para alternar o mirror rapidamente"""
        
        tips_widget = tk.Text(tips_frame, wrap=tk.WORD, height=4, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        tips_widget.insert(1.0, tips_text)
        tips_widget.configure(state="disabled")
        tips_widget.pack(fill=tk.X)

    def _show_help_generic(self, topic_key, title):
        """Mostra conteúdo genérico para tópicos não implementados"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título
        title_label = ttk.Label(content_frame, text=f"Ajuda: {title}", 
                            font=("Arial", 16, "bold"))
        title_label.pack(anchor="w", pady=(0, 15))
        
        # Mensagem
        msg_text = f"""Conteúdo da ajuda para "{title}" será adicionado em breve.

    Se você precisa de ajuda com esta funcionalidade:
    1. Experimente usar a função e observe o comportamento
    2. Consulte outros tópicos relacionados na lista à esquerda  
    3. Leia os arquivos de referência do FDS/FAdC

    Tópico ID: {topic_key}"""
        
        msg_widget = tk.Text(content_frame, wrap=tk.WORD, height=8, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        msg_widget.insert(1.0, msg_text)
        msg_widget.configure(state="disabled")
        msg_widget.pack(fill=tk.X)

    def _show_help_tool_sensor(self):
        """Ajuda para a Ferramenta Sensor"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título
        title_label = ttk.Label(content_frame, text="Sensores", 
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))
        
        # Descrição
        desc_text = """A ferramenta Sensor permite posicionar sensores de detecção de trens no trackplan. Estes sensores são fundamentais para o sistema de detecção FDS."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=2, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))
        
        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Selecione a ferramenta 'Sensor' na barra de ferramentas",
            "2. Escolha o ângulo desejado (0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°)",
            "3. Configure o mirror se necessário",
            "4. Clique no canvas para posicionar o sensor",
            "5. Configure se o sensor tem FMA associado (opcional)"
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)
        
        # Atalhos
        shortcuts_frame = ttk.LabelFrame(content_frame, text="Atalhos de Teclado", padding="15")
        shortcuts_frame.pack(fill=tk.X, pady=(0, 20))
        
        shortcuts = [
            ("S", "Selecionar ferramenta Sensor"),
            ("M", "Alternar Mirror"),
            ("Mouse Wheel", "Alterar ângulo"),
            ("Delete", "Remover sensor selecionado"),
            ("Ctrl+S", "Configurações do sensor selecionado")
        ]
        
        for key, action in shortcuts:
            shortcut_frame = ttk.Frame(shortcuts_frame)
            shortcut_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(shortcut_frame, text=f"{key}:", font=("Courier", 10, "bold"), 
                     width=15).pack(side=tk.LEFT)
            ttk.Label(shortcut_frame, text=action, font=("Arial", 10)).pack(side=tk.LEFT)

        # Dicas
        tips_frame = ttk.LabelFrame(content_frame, text="💡 Dicas", padding="15")
        tips_frame.pack(fill=tk.X)

        tips_text = """• Lembre-se de configurar os sensores.
• Certifique-se de que os sensores estão posicionados corretamente no trackplan.
• Caso um sensor possua FMAs, configure o sensor nas configurações ou com o atalho Ctrl + S."""

        tips_widget = tk.Text(tips_frame, wrap=tk.WORD, height=4, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        tips_widget.insert(1.0, tips_text)
        tips_widget.configure(state="disabled")
        tips_widget.pack(fill=tk.X)

    def _show_help_tool_fma(self):
        """Ajuda para a Ferramenta FMA"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título
        title_label = ttk.Label(content_frame, text="FMAs",
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))
              
        # Descrição
        desc_text = """A ferramenta FMA permite posicionar FMAs no trackplan. Tais FMAs estarão sempre cercadas por sensores, que delimitarão a área da mesma.
As FMAs podem podem ter seus nomes e ids alterados. É possível também adicionar trilhos, chaves e links como trilhos associados a sua área. Também como determinar quais sensores serão os delimitadores de sua área. É possível destacar os limites da FMA, onde os elementos a ela associada, serão destacados em azul."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=6, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))        

        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Selecione a ferramenta 'FMA' na barra de ferramentas",
            "2. Escolha o ângulo desejado (0°, 90°, 180°, 270°)",
            "3. Clique no canvas para posicionar a FMA",
            "4. Selecione a FMA e utilize o atalho 'Ctrl + F' para abrir a janela de configuração da FMA",
            "5. Configure os sensores delimitadores, trilhos associados e outros parâmetros conforme necessário"
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)
        
        # Atalhos
        shortcuts_frame = ttk.LabelFrame(content_frame, text="Atalhos de Teclado", padding="15")
        shortcuts_frame.pack(fill=tk.X, pady=(0, 20))
        
        shortcuts = [
            ("F", "Selecionar ferramenta Sensor"),
            ("M", "Alternar Mirror"),
            ("Mouse Wheel", "Alterar ângulo"),
            ("Delete", "Remover sensor selecionado"),
            ("Ctrl+F", "Abrir as configurações da FMA")
        ]
        
        for key, action in shortcuts:
            shortcut_frame = ttk.Frame(shortcuts_frame)
            shortcut_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(shortcut_frame, text=f"{key}:", font=("Courier", 10, "bold"), 
                     width=15).pack(side=tk.LEFT)
            ttk.Label(shortcut_frame, text=action, font=("Arial", 10)).pack(side=tk.LEFT)

        # Dicas
        tips_frame = ttk.LabelFrame(content_frame, text="💡 Dicas", padding="15")
        tips_frame.pack(fill=tk.X)
        
        tips_text = """• As configurações da FMA podem ser acessadas selecionando a FMA e clicando em:
    Configurações -> Edição ->  Editar FMA.
• Fazer uma cópia de uma FMA irá desconfigurá-la, removendo trilhos associados, nomes e id.
• Não esqueça de configurar e testar os limites das FMAs e elementos associados.
• FMAs não possuem mirror."""
        
        tips_widget = tk.Text(tips_frame, wrap=tk.WORD, height=5, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        tips_widget.insert(1.0, tips_text)
        tips_widget.configure(state="disabled")
        tips_widget.pack(fill=tk.X)

    def _show_help_tool_select(self):
        """Ajuda para a ferramenta de seleção"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título
        title_label = ttk.Label(content_frame, text="Seleçao",
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))
        
        # Descrição
        desc_text = """A ferramenta de seleção é utilizada para selecionar elementos no trackplan, linhas ou colunas. Possui diversas funcionalidades para facilitar a manipulação dos elementos.
Abaixo será comentado sobre algumas das funções que a ferramenta de seleção proporciona. Ao selecioanr um elemento, uma borda vermelha marcará o item selecionado, podendo ser copiar, recortar ou até deletar o item. Caso selecione algum quadrado vazio do grid, uma borda azul clara aparecerá.
Também é possível selecionar uma matriz(x1,y1,x2,y2) utilizando Ctrl + Shift + Clique esquerdo para começar a seleção do ponto(x1,y1) e depois selecione o ponto(x2,y2), fazendo a seleção de todos os elementos na área, podendo serem copiados ou recortados para serem colados posteriormente."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=8, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))
        
        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Selecione a ferramenta 'Seleção' na barra de ferramentas",
            "2. Selecione algum elemento no canvas",
            "3. Utilize algumas das funções possíveis.",
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)
        
        # Atalhos
        shortcuts_frame = ttk.LabelFrame(content_frame, text="Atalhos de Teclado", padding="15")
        shortcuts_frame.pack(fill=tk.X, pady=(0, 20))
        
        shortcuts = [
            ("V", "Selecionar ferramenta Seleção"),
            ("Clique esquerdo com a ferramenta", "Seleciona elemento ou vazio"),
            ("Delete", "Remover elemento selecionado"),
            ("Ctrl+C", "Copia elemento selecionado"),
            ("Ctrl+F", "Configura uma FMA (Apenas se uma FMA estiver selecionada)"),
            ("Ctrl+S", "Configura um Sensor(Apenas se um Sensor estiver selecionado)"),
            ("Ctrl+Shift+Clique", "Começa a seleção múltipla, após o segundo clique, uma área é selecionada")
        ]
        
        for key, action in shortcuts:
            shortcut_frame = ttk.Frame(shortcuts_frame)
            shortcut_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(shortcut_frame, text=f"{key}:", font=("Courier", 10, "bold"), width=10).pack(side=tk.LEFT)
            ttk.Label(shortcut_frame, text=action, font=("Arial", 10)).pack(side=tk.LEFT)

        # Dicas
        tips_frame = ttk.LabelFrame(content_frame, text="💡 Dicas", padding="15")
        tips_frame.pack(fill=tk.X)
        
        tips_text = """• A seleção de um elemento altera as informações presentes no canto inferior esquerdo, permitindo a visualização da célula e do Id do item selecionado.
• Leia mais sobre visualização múltipla na aba da mesma."""
        
        tips_widget = tk.Text(tips_frame, wrap=tk.WORD, height=4, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        tips_widget.insert(1.0, tips_text)
        tips_widget.configure(state="disabled")
        tips_widget.pack(fill=tk.X)

    def _show_help_tool_eraser(self):
        """Ajuda para a ferramenta de borracha"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título
        title_label = ttk.Label(content_frame, text="Borracha",
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))
        
        # Descrição
        desc_text = """A ferramenta de borracha é utilizada para apagar elementos no trackplan. Após sua seleção, com o botão esquerdo, selecione elementos que deseja deletar."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=2, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))
        
        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Selecione a ferramenta 'Borracha' na barra de ferramentas",
            "2. Escolha algum elemento no canvas que queira deletar",
            "3. Clique com o botão esquerdo sobre o item para deletá-lo."
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)
        
        # Atalhos
        shortcuts_frame = ttk.LabelFrame(content_frame, text="Atalhos de Teclado", padding="15")
        shortcuts_frame.pack(fill=tk.X, pady=(0, 20))
        
        shortcuts = [
            ("E", "Selecionar ferramenta Borracha"),
            ("Clique esquerdo com a ferramenta", "Remove o elemento"),
            ("Delete", "Apaga elemento selecionado pela ferramente Seleção")
        ]
        
        for key, action in shortcuts:
            shortcut_frame = ttk.Frame(shortcuts_frame)
            shortcut_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(shortcut_frame, text=f"{key}:", font=("Courier", 10, "bold"), width=15).pack(side=tk.LEFT)
            ttk.Label(shortcut_frame, text=action, font=("Arial", 10)).pack(side=tk.LEFT)

        # Dicas
        tips_frame = ttk.LabelFrame(content_frame, text="💡 Dicas", padding="15")
        tips_frame.pack(fill=tk.X)
        
        tips_text = """• Para a remoção de vários elementos, utilize outras ferramentas, como selecionar tudo ou o botão de limpar tudo, que apaga todos os elementos do canvas.
• Elementos falsamente deletados podem ser restituídos utilizando o Ctrl + Z."""
        tips_widget = tk.Text(tips_frame, wrap=tk.WORD, height=4, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        tips_widget.insert(1.0, tips_text)
        tips_widget.configure(state="disabled")
        tips_widget.pack(fill=tk.X)

    def _show_help_grid_config(self):
        """Ajuda para a configuração da grade"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título
        title_label = ttk.Label(content_frame, text="Configurar Grade",
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20)) 

        # Descrição
        desc_text = """A configuração da grade permite ajustar a visualização do canvas, facilitando o alinhamento e a organização dos elementos. 
As dimensões do grid podem ser alteradas nas configurações do canvas, na opção de 'Configurar Grade'."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack(fill=tk.X, pady=(0, 20))

        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)

        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Na aba Designer Trackplan, vá em Configurações -> Configurar Grade.",
            "2. Selecione um tamanho máximo para colunas e linhas que serão apresentadas no canvas.",
            "3. O tamanho do canvas pode ser alterado a qualquer instante durante o processo de criação, não perdendo nada."
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)

        # Dicas
        tips_frame = ttk.LabelFrame(content_frame, text="💡 Dicas", padding="15")
        tips_frame.pack(fill=tk.X)
        
        tips_text = """• Lembre-se que as colunas e linhas começam no 0 e vão até o valor máximo escolhido. Portanto, o número de linhas e colunas será sempre número de (linhas+1,colunas+1).
• Ao remover ou inserir colunas, lembre-se que as dimensões do canvas serão alteradas.
• Ao carregar um Trackplan, suas dimensões serão automaticamente aplicadas ao canvas."""
        
        tips_widget = tk.Text(tips_frame, wrap=tk.WORD, height=4, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        tips_widget.insert(1.0, tips_text)
        tips_widget.configure(state="disabled")
        tips_widget.pack(fill=tk.X)

    def _show_help_cubicles_overview(self):
        """Ajuda para a visão geral dos cubiculos"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título
        title_label = ttk.Label(content_frame, text="Visão Geral dos Cubículos",
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))
        
        # Descrição
        desc_text = """Os cubículos são elementos fundamentais na criação do programa FDS. Eles permitem visualizar de maneira simplificada cada componente de um rack de maneira intuitiva. 
Cada cubículo pode ser configurado individualmente, podendo ser adicionados COMs, AEBs, IOExbs, ou até Espaços vazios para futara configuração. O componente Psc obtem sempre o primeiro slot."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=6, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X)
        
        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Para criar o seu primeiro cubículo, selecione a opção na esquerda '➕ Novo Cubículo'",
            "2. Na aba Básico, defina itens como Nome do Cubículo e quantidade de slots",
            "3. Na aba Layout do Rack, adicione os componentes desejados em cada slot do rack",
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)

        # Dicas
        tips_frame = ttk.LabelFrame(content_frame, text="💡 Dicas", padding="15")
        tips_frame.pack(fill=tk.X)
        
        tips_text = """• Não preocupe-se com os IDs dos cubículos, eles serão preenchidos automaticamente.
• Atente-se aos IDs dos componentes e seus prefixos. Eles serão preenchidos automaticamente. Qualquer dúvida, procure a aba de ajuda do componente Em 'Tipos de Componentes'."""
        
        tips_widget = tk.Text(tips_frame, wrap=tk.WORD, height=4, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        tips_widget.insert(1.0, tips_text)
        tips_widget.configure(state="disabled")
        tips_widget.pack(fill=tk.X)

    def _show_help_keyboard_shortcuts(self):
        """Ajuda para Atalhos de Teclado"""
        content_frame = tk.Frame(self.help_content_frame, bg="#f0f0f0")
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título
        title_label = ttk.Label(content_frame, text="Atalhos de Teclado", 
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))
        
        # Ferramentas
        tools_frame = ttk.LabelFrame(content_frame, text="Seleção de Ferramentas", padding="15")
        tools_frame.pack(fill=tk.X, pady=(0, 15))
        
        tools_shortcuts = [
            ("T", "Trilho"),
            ("L", "Link"),
            ("S", "Sensor"),
            ("C", "Chave"),
            ("F", "FMA"),
            ("V", "Seleção"),
            ("E", "Borracha")
        ]
        
        for key, tool in tools_shortcuts:
            shortcut_frame = ttk.Frame(tools_frame)
            shortcut_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(shortcut_frame, text=f"{key}:", font=("Courier", 11, "bold"), 
                     width=2, background="#e3f2fd").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(shortcut_frame, text=tool, font=("Arial", 10)).pack(side=tk.LEFT)
        
        # Edição
        edit_frame = ttk.LabelFrame(content_frame, text="Edição", padding="15")
        edit_frame.pack(fill=tk.X, pady=(0, 15))
        
        edit_shortcuts = [
            ("Ctrl+C", "Copiar seleção"),
            ("Ctrl+O", "Carregar Trackplan"),
            ("Ctrl+B", "Salvar Trackplan"),
            ("Ctrl+S", "Configurar Sensor selecionado"),
            ("Ctrl+F", "Configurar FMA selecionada"),
            ("Ctrl+X", "Recortar seleção"),
            ("Ctrl+V", "Colar"),
            ("Ctrl+Z", "Desfazer"),
            ("Ctrl+Y", "Refazer"),
            ("Ctrl+A", "Selecionar todos os elementos do Trackplan"),
            ("Delete", "Excluir selecionado"),
            ("Ctrl+Shift+Clique", "Seleção múltipla")
        ]
        
        for key, action in edit_shortcuts:
            shortcut_frame = ttk.Frame(edit_frame)
            shortcut_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(shortcut_frame, text=f"{key}:", font=("Courier", 10, "bold"), 
                     width=18, background="#fff3e0").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(shortcut_frame, text=action, font=("Arial", 10)).pack(side=tk.LEFT)
        
        # Modificadores
        modifiers_frame = ttk.LabelFrame(content_frame, text="Modificadores", padding="15")
        modifiers_frame.pack(fill=tk.X)
        
        modifiers_shortcuts = [
            ("M", "Alternar Mirror"),
            ("Mouse Wheel", "Alterar ângulo da ferramenta"),
        ]
        
        for key, action in modifiers_shortcuts:
            shortcut_frame = ttk.Frame(modifiers_frame)
            shortcut_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(shortcut_frame, text=f"{key}:", font=("Courier", 10, "bold"), 
                     width=13, background="#f3e5f5").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Label(shortcut_frame, text=action, font=("Arial", 10)).pack(side=tk.LEFT)

    def _show_help_xml_view_modes(self):
        """Mostra ajuda sobre os modos de visualização XML"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Título principal
        title_label = ttk.Label(content_frame, text="Modos de Visualização", 
                               font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 15))
        
        # Descrição geral
        desc_text = """O sistema possui uma área para visualizar ambos arquivos XML, Trackplan.xml e FdsConfig.xml.
Para facilitar a visualização e análise, o Praxis apresenta três distintas formas de visualizar o código XML de ambos arquivos.
Para alterar o modo de visualização, utilize o botão Visualização e altere o tamanho da fonte com a opção ao lado. O sistema ainda conta com a adição de pesquisa por texto."""
        
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack()
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W, pady=(0, 15))

        # Frame principal para os modos
        modes_frame = ttk.LabelFrame(content_frame, text="Modos Disponíveis", padding="15")
        modes_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Modo 1: Em Abas
        mode1_frame = ttk.Frame(modes_frame)
        mode1_frame.pack(fill=tk.X, pady=(0, 15))
        
        mode1_title = ttk.Label(mode1_frame, text="Em Abas", 
                               font=("Arial", 13, "bold"), foreground="#1976d2")
        mode1_title.pack(anchor=tk.W)
        
        mode1_desc = ttk.Label(mode1_frame, 
                              text="• Sistema dividido em abas onde cada preview aparece por vez\n• Aumenta o espaço de análise\n• Ideal para análise individual de cada arquivo",
                              font=("Arial", 10), wraplength=550, justify=tk.LEFT)
        mode1_desc.pack(anchor=tk.W, padx=(20, 0), pady=(5, 0))
        
        # Modo 2: Lado a Lado
        mode2_frame = ttk.Frame(modes_frame)
        mode2_frame.pack(fill=tk.X, pady=(0, 15))
        
        mode2_title = ttk.Label(mode2_frame, text="Lado a Lado", 
                               font=("Arial", 13, "bold"), foreground="#388e3c")
        mode2_title.pack(anchor=tk.W)
        
        mode2_desc = ttk.Label(mode2_frame, 
                              text="• Separação vertical da tela\n• Possibilita ver ambos previews simultaneamente\n• Ideal para comparação entre arquivos",
                              font=("Arial", 10), wraplength=550, justify=tk.LEFT)
        mode2_desc.pack(anchor=tk.W, padx=(20, 0), pady=(5, 0))
        
        # Modo 3: Vertical
        mode3_frame = ttk.Frame(modes_frame)
        mode3_frame.pack(fill=tk.X)
        
        mode3_title = ttk.Label(mode3_frame, text="Vertical", 
                               font=("Arial", 13, "bold"), foreground="#f57c00")
        mode3_title.pack(anchor=tk.W)
        
        mode3_desc = ttk.Label(mode3_frame, 
                              text="• Corte horizontal que separa ambos códigos\n• Deixa uma visão vertical dos arquivos\n• Ideal para análise de arquivos longos",
                              font=("Arial", 10), wraplength=550, justify=tk.LEFT)
        mode3_desc.pack(anchor=tk.W, padx=(20, 0), pady=(5, 0))
        
        # Nota importante
        note_frame = ttk.LabelFrame(content_frame, text="⚠️ Importante", padding="10")
        note_frame.pack(fill=tk.X, pady=(15, 0))
        
        note_text = "Lembre-se: A visualização é apenas para análise. Caso queria alterar os arquivos manualmente, você deve salvar os arquivos conforme descrito na seção 'Salvar Arquivos' e fazer a alteração em um software de edição (Notepad++)."
        note_label = ttk.Label(note_frame, text=note_text, 
                              font=("Arial", 10, "italic"), wraplength=600, justify=tk.LEFT)
        note_label.pack(anchor=tk.W)

    def _show_help_xml_update_preview(self):
        """Mostra ajuda sobre atualizar preview XML"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Título principal
        title_label = ttk.Label(content_frame, text="Atualizar Preview", 
                               font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 15))
        
        # Descrição da funcionalidade
        main_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        main_frame.pack(fill=tk.X, pady=(0, 20))
        
        desc_text = """A função de Atualizar Preview prepara ambos códigos com as últimas atualizações feitas nas etapas anteriores no processo de configuração do FDS."""
        
        desc_label = ttk.Label(main_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)
        
        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        steps = [
            "1. Faça as configurações desejadas nas abas FdsConfig e Designer Trackplan",
            "2. Clique no botão 'Atualizar Preview' na aba de Visualização XML",
            "3. Aguarde o processamento das alterações",
            "4. Visualize os códigos XML atualizados nos painéis de preview",
            "5. Utilize as funções de edição para auxiliar na visualização"
        ]
        
        for step in steps:
            step_label = ttk.Label(usage_frame, text=step, 
                                  font=("Arial", 10), wraplength=550, justify=tk.LEFT)
            step_label.pack(anchor=tk.W, pady=2)

        # Dicas
        tips_frame = ttk.LabelFrame(content_frame, text="💡 Dicas", padding="15")
        tips_frame.pack(fill=tk.X)
        
        tips = [
            "• Sempre atualize o preview antes de salvar os arquivos",
            "• O preview mostra exatamente como os arquivos serão salvos",
            "• As alterações feitas no preview não afetam as configurações",
            "• O preview é de visualização somente"
        ]
        
        for tip in tips:
            tip_label = ttk.Label(tips_frame, text=tip, 
                                 font=("Arial", 10), wraplength=550, justify=tk.LEFT)
            tip_label.pack(anchor=tk.W, pady=2)

    def _show_help_create_cubicle(self):
        """Ajuda a respeito da criação de cubículos"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        #Titulo principal
        title_label = ttk.Label(content_frame, text="Criar Cubículo",
                                 font=("Arial", 16, "bold"))
        title_label.pack(anchor=tk.W, pady=(0, 15))

        # Descrição da funcionalidade
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))

        desc_text = """A funcionalidade de criar cubículos permite adicionar novos cubículos ao layout do sistema. Cada cubículo pode ser configurado com um nome único e uma quantidade específica de slots. Adicione os elementos necessários e salve-os."""

        desc_label = ttk.Label(desc_frame, text=desc_text,
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)

        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Selecione a opção '➕ Novo Cubículo' na barra lateral esquerda",
            "2. Preencha as informações básicas na aba da direita e salve as configurações",
            "3. Configure o Layout do Rack adicionando os componentes desejados e seus IDs",
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)

        # Dicas
        tips_frame = ttk.LabelFrame(content_frame, text="💡 Dicas", padding="15")
        tips_frame.pack(fill=tk.X)

        tips_text = """• Lembre-se de conferir os dados configurados.
• Os cubículos podem ser arrastados na lista de Cubículos Existentes para ordená-los. Isso irá alterar os Ids automaticamente.
• A lista de 'Cubículos Existentes' também mostra informações como status de preenchimento, quantidade de AEBs e número total de Slots"""

        tips_widget = tk.Text(tips_frame, wrap=tk.WORD, height=5, font=("Arial", 10),
                            bg="#f0f0f0", relief="flat")
        tips_widget.insert(1.0, tips_text)
        tips_widget.configure(state="disabled")
        tips_widget.pack(fill=tk.X)

    def _show_help_rack_layout(self):
        """Ajuda para o Layout do Rack"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)
        
        # Título
        title_label = ttk.Label(content_frame, text="Layout do Rack", 
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))
        
        # Descrição
        desc_text = """O layout do rack é uma simplificação visual do rack utilizado em campo. Onde cada slot é um componente alocado no rack.
Seu primeiro Slot é sempre para o Psc, que é um componente de suprimento de energia. Logo em seguida, é de costume, adicionar a componente COM.
É preciso ficar atento ao configurar os racks, sempre fazendo uma analise ao arquivo .dwg ou .pdf, que está sendo utilizado de referência para o desenvolvimento do FDS."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=4, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))

        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Crie um cubículo e configure-o. Leia mais sobre na aba acima 'Criar Cubículo'",
            "2. Selecione o slot desejado no cubículo para adicionar um componente",
            "3. Selecione entre os tipos de componentes",
            "4. Adicione o seu Id e selecione 'Aplicar'. Verifique se o nome atribuído está correto.",
            "5. Repita até terminar o cubículo"
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)

    def _show_help_component_psc(self):
        """Ajuda para o componente PSC"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        #Título
        title_label = ttk.Label(content_frame, text="Componente PSC",
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))

        #Descrição
        desc_text = """O componente PSC (Power Supply with Crowbar) é responsável por gerenciar a distribuição de energia no sistema FDS. Ele garante que todos os componentes recebam a energia necessária para funcionar corretamente.
Ao criar um cubículo, esse é o primeiro componente criado automaticamente e ficará sempre no Slot 1."""
        
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=3, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))

    def _show_help_component_com(self):
        """Ajuda para o componente COM"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        #Título
        title_label = ttk.Label(content_frame, text="Componente COM",
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))

        #Descrição
        desc_text = """O componente COM (Communication Board) é responsável por gerenciar a comunicação entre os diversos compontentes de diagnósticos (AEBs) utilizando um CAN bus (Controller Area Network bus), um protocolo de comunicação entre aparelhos eletroeletrônicos.
A COM comunica com aparelho FDS via Ethernet, fazendo essa função de transporte de informações entre os aparelhos de diagnóstico e o sistema FDS."""
        
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=3, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))

        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Crie um cubículo e configure-o. Leia mais sobre na aba de ajuda 'Criar Cubículo'",
            "2. Selecione o slot desejado no cubículo para adicionar o componente COM",
            "3. Configure o seu ID. Note que o seu prefixo '0' será adicionado conforme é digitado o ID.",
            "4. Verifique se o nome possui a estrutura correta. 'COM+ID(sem prefixo)'",
            "5. Verifique também o CAN ID, que deverá ser o ID sem prefixo"
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)

    def _show_help_component_aeb(self):
        """Ajuda para o componente AEB"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        #Título
        title_label = ttk.Label(content_frame, text="Componente AEB",
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))

        #Descrição
        desc_text = """O componente AEB (Advanced Evaluation Board) é responsável por administrar e diagnosticar as informações vindas dos ativos em campo e comunicar as COMs."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=2, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))

        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Crie um cubículo e configure-o. Leia mais sobre na aba de ajuda 'Criar Cubículo'",
            "2. Selecione o slot desejado no cubículo para adicionar o componente AEB",
            "3. Configure o seu ID. Note que o seu prefixo '1' será adicionado conforme é digitado o ID.",
            "4. Verifique se o nome possui a estrutura correta. 'AEB+ID(sem prefixo)'",
            "5. Verifique também o CAN ID, que deverá ser o ID sem prefixo",
            "6. Verifique também o Ref ID, que deverá ser o prefixo '2'+'ID(sem prefixo)'"
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)

    def _show_help_component_ioexb(self):
        """Ajuda para o componente IoExb"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        #Título
        title_label = ttk.Label(content_frame, text="Componente IoExb",
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))

        #Descrição
        desc_text = """O componente IoExb (Input/Output Board) é responsável por fazer o output das informações do sistema de contadores de eixo."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=2, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))

        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Crie um cubículo e configure-o. Leia mais sobre na aba de ajuda 'Criar Cubículo'",
            "2. Selecione o slot desejado no cubículo para adicionar o componente IoExb",
            "3. Configure o seu ID. Note que o seu prefixo '5' será adicionado conforme é digitado o ID.",
            "4. O seu nome será sempre IO-EXB",
            "5. Verifique também o Ref ID, que deverá ser o prefixo '1'+'ID(sem prefixo)'"
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)

    def _show_help_component_empty(self):
        """Ajuda para o componente Slot Vazio"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        #Título
        title_label = ttk.Label(content_frame, text="Slot Vazio",
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))

        #Descrição
        desc_text = """O slot vazio possui um ID que não deverá ser alterado. Ele é calculado automaticamente pelo sistema. É importante adicioná-los quando necessário, mostrando que será completo futuramente."""

        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=3, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))


    def _show_help_cubicle_validation(self):
        """Ajuda para a aba de validação do cubículo"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.X, padx=20, pady=20)

        #Título
        title_label = ttk.Label(content_frame, text="Cubículo: Validação",
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor="w", pady=(0, 20))

        #Descrição
        desc_text = """ A aba de validação do cubículo permite verificar se todos os componentes foram configurados corretamente. Ela analisa os IDs, nomes, quantidade de elementos e outras propriedades para garantir que não haja conflitos ou erros.
Caso seja encontrado algum problema, o sistema transmite um aviso ou erros por texto explicando onde foi encontrado a interferência.
Nesta mesma aba, opções de visualização do código XML, tanto de um cubículo individual, tanto de todo o rack. Contando também com a opção de salvar o arquivo Trackplan.xml com apenas os cubículos."""
        
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame.pack()
        desc_label = tk.Text(desc_frame, wrap=tk.WORD, height=3, font=("Arial", 11),
                            bg="#f0f0f0", relief="flat")
        desc_label.insert(1.0, desc_text)
        desc_label.configure(state="disabled")
        desc_label.pack(fill=tk.X, pady=(0, 20))

        # Como usar
        usage_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="15")
        usage_frame.pack(fill=tk.X, pady=(0, 20))
        
        usage_steps = [
            "1. Crie um cubículo e configure-o. Leia mais sobre na aba de ajuda 'Criar Cubículo'",
            "2. Na aba validação, selecione na lista de 'Cubículos Existentes', a esquerda, um dos cubículos",
            "3. Escolha uma das opções: Validar cubículo, Gerar XML ou Salvar XML",
            "4. O botão de Gerar XML irá mostrar o código XML do cubículo selecionado na área Preview do XML",
            "5. O botão XML Todos Cubículos mostrará no mesmo local do Gerar XML"
        ]
        
        for step in usage_steps:
            ttk.Label(usage_frame, text=step, font=("Arial", 10)).pack(anchor="w", pady=2)

    def _show_help_xml_save_files(self):
        """Mostra ajuda sobre salvar arquivos XML"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Título principal
        title_label = ttk.Label(content_frame, text="Salvar Arquivos", 
                               font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 15))
        
        # Descrição das opções de salvamento
        desc_primeiro_text = """O sistema possui algumas maneiras de salvar o seu progresso e colocar o FDS para funcionar com o seu novo layout criado. É possível salvar em partes ou salvar até o arquivo já zipado, FdsRecovery.zip, que é utilizado para fazer a atualização do aparelho FDS. O arquivo FdsRecovery.zip é uma pasta compactada que possui ambos arquivos Trackplan.xml e FdsConfig.xml.

Salvar Trackplan.xml: Encontra um diretório para salvar o Trackplan.xml
Salvar FdsConfig.xml: Encontra um diretório para salvar o FdsConfig.xml
Gerar FdsRecovery.zip: Encontra um diretório para salvar o FdsRecovery.zip
Salvar Tudo: Encontra um diretório para salvar o FdsRecovery.zip mais ambos arquivos não compactados. Estrutura utilizada na MRS para salvamento em pastas de projeto."""

        desc_frame_primeiro = ttk.LabelFrame(content_frame, text="Descrição", padding="10")
        desc_frame_primeiro.pack()

        desc_text_primeiro = tk.Text(desc_frame_primeiro, wrap=tk.WORD, height=5, font=("Arial", 11),
                                    bg="#f0f0f0", relief="flat")
        desc_text_primeiro.insert(1.0, desc_primeiro_text)
        desc_text_primeiro.configure(state="disabled")
        desc_text_primeiro.pack(fill=tk.X, pady=(0,20))

        # Descrição do processo
        desc_frame = ttk.LabelFrame(content_frame, text="Processo de Atualização do Layout FDS", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))
        
        desc_text = """Para que o layout atual do FDS seja atualizado, é necessário salvar o FdsRecovery.zip dentro de um pendrive vazio e conectar em alguma das portas USB do sistema FDS."""
        
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)
        
        # Arquivos necessários
        files_frame = ttk.LabelFrame(content_frame, text="Arquivos Necessários", padding="15")
        files_frame.pack(fill=tk.X, pady=(0, 20))
        
        files_list = [
            "1. FdsConfig.xml - Configurações do sistema FDS",
            "2. Trackplan.xml - Layout dos trilhos e cubículos", 
            "3. FdsRecovery.zip - FdsConfig.xml e Trackplan.xml compactados"
        ]
        
        for file_item in files_list:
            file_label = ttk.Label(files_frame, text=file_item, 
                                  font=("Arial", 10), wraplength=550, justify=tk.LEFT)
            file_label.pack(anchor=tk.W, pady=2)
        
        # Passo a passo
        steps_frame = ttk.LabelFrame(content_frame, text="Passo a Passo", padding="15")
        steps_frame.pack(fill=tk.X, pady=(0, 20))
        
        steps = [
            "1. Certifique-se de que o preview foi atualizado com suas últimas alterações",
            "2. Clique em 'Salvar Arquivos' na aba de Visualização XML",
            "3. Escolha um diretório no seu pendrive para salvar os arquivos",
            "4. Aguarde a conclusão do salvamento do(s) arquivo(s)",
            "5. Ejete o pendrive com segurança do computador",
            "6. Conecte o pendrive em uma das portas USB do aparelho FDS",
            "7. O sistema detectará automaticamente os novos arquivos",
            "8. Aguarde a aplicação das configurações e conecte a Interface Web"
        ]
        
        for i, step in enumerate(steps, 1):
            step_frame = ttk.Frame(steps_frame)
            step_frame.pack(fill=tk.X, pady=2)
            
            step_label = ttk.Label(step_frame, text=step, 
                                  font=("Arial", 10), wraplength=520, justify=tk.LEFT)
            step_label.pack(anchor=tk.W)
        
        # Avisos importantes
        warnings_frame = ttk.LabelFrame(content_frame, text="Avisos Importantes", padding="15")
        warnings_frame.pack(fill=tk.X)
        
        warnings = [
            "• Sempre faça backup dos arquivos originais antes de aplicar alterações",
            "• Certifique-se de que o pendrive está formatado corretamente (FAT32 recomendado)",
            "• Verifique se há espaço suficiente no pendrive para os três arquivos",
            "• Não remova o pendrive durante o processo de aplicação das configurações",
            "• Por via das dúvidas, guarde o FdsRecovery.zip para restaurar configurações anteriores"
        ]
        
        for warning in warnings:
            warning_label = ttk.Label(warnings_frame, text=warning, 
                                    font=("Arial", 10), wraplength=550, justify=tk.LEFT, foreground="#d32f2f")
            warning_label.pack(anchor=tk.W, pady=2)

    def _show_help_xml_validation(self):
        """Mostra ajuda sobre validação dos arquivos XML"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Título principal
        title_label = ttk.Label(content_frame, text="Validação XSD", 
                               font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 20))
        
        # Descrição do processo
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))
        
        desc_text = """O Praxis conta com uma validação utilizando XSD para os arquivos XML. A validação se da utilizando um arquivo XSD que age como um regulamentador de tipos de valores que podem ocupar certas variáveis nos arquivos FdsConfig.xml e Trackplan.xml.
Tal adição certifica de que o código que sai ao final de todo processo está pronto para rodar no sistema FDS, evitando 100% os erros de formatação.
Para fazer a verificação do seu programa, utilize o botão 'Validador'. Uma varredura no programa será feita em busca de erros, assim que confirmado que não há problemas, o programa está pronto para exportação."""
        
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)

    def _show_help_undo_redo(self):
        """Mostra ajuda sobre as opções de refazer/desfazer"""        
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Título principal
        title_label = ttk.Label(content_frame, text="Desfazer/Refazer", 
                               font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 20))
        
        # Descrição do processo
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))
        
        desc_text = """O Praxis possui funções implementadas de undo e redo para o processo de criação do Designer Trackplan apenas. As funções fazem o esperado, desfazem ou refazem alguma ação.
Posuem atalhos tradicionais: Ctrl + Z para desfazer(undo) e Ctrl + Y para refazer(redo). """    
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)

    def _show_help_copy_paste(self):
        """Mostra ajuda sobre a diferentes formas de copiar e colar"""        
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Título principal
        title_label = ttk.Label(content_frame, text="Copiar/Colar", 
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 20))
        
        # Descrição do processo
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))
        
        desc_text = """O Praxis possui a possibilidade e copiar e colar elementos do layout Trackplan. Podendo copiar elementos sozinhos, em grupo ou linhas e colunas específicas."""    
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                            font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)

        # Frame principal para os metodos populares de copy/paste
        modes_frame = ttk.LabelFrame(content_frame, text="Modos Disponíveis", padding="15")
        modes_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Método 1: Sozinho
        mode1_frame = ttk.Frame(modes_frame)
        mode1_frame.pack(fill=tk.X, pady=(0, 15))
        
        mode1_title = ttk.Label(mode1_frame, text="Elemento Sozinho", 
                               font=("Arial", 13, "bold"), foreground="#1976d2")
        mode1_title.pack(anchor=tk.W)
        
        text_modo_sozinho = """1. Selecione a ferramenta 'Selecionar' na aba de ferramentas
2. Selecione o elemento que será copiado
3. Utilize o Atalho Ctrl+C ou vá em 'Configurações' -> 'Edição' -> 'Copiar'
4. Caso necessário, o Praixs possui a opção de 'Recortar', localizada entre as funções de 'Copiar' e 'Colar'
5. Selecione a célula destino, onde você quer colar
6. Utilize o Atalho Ctrl+V ou vá em 'Configurações' -> 'Edição' -> 'Colar'"""

        mode1_desc = ttk.Label(mode1_frame, 
                              text=text_modo_sozinho,
                              font=("Arial", 10), wraplength=550, justify=tk.LEFT)
        mode1_desc.pack(anchor=tk.W, padx=(20, 0), pady=(5, 0))
        
        # Método 2: Em grupo
        mode2_frame = ttk.Frame(modes_frame)
        mode2_frame.pack(fill=tk.X, pady=(0, 15))
        
        mode2_title = ttk.Label(mode2_frame, text="Em grupo", 
                               font=("Arial", 13, "bold"), foreground="#388e3c")
        mode2_title.pack(anchor=tk.W)
        
        text_modo_grupo = """1. Selecione a ferramenta 'Selecionar' na aba de ferramentas
2. Com o Ctrl segurado, selecione os elementos que quer selecionar
3. Utilize o Atalho Ctrl+C ou vá em 'Configurações' -> 'Edição' -> 'Copiar'
4. Caso necessário, o Praixs possui a opção de 'Recortar', localizada entre as funções de 'Copiar' e 'Colar'
5. Selecione a célula destino, onde você quer colar
6. Nota-se, a célula destino irá receber o elemento mais à superior esquerda possível dos elementos copiados.
7. Utilize o Atalho Ctrl+V ou vá em 'Configurações' -> 'Edição' -> 'Colar'"""

        mode2_desc = ttk.Label(mode2_frame, 
                              text=text_modo_grupo,
                              font=("Arial", 10), wraplength=550, justify=tk.LEFT)
        mode2_desc.pack(anchor=tk.W, padx=(20, 0), pady=(5, 0))
        
        # Método 3: Selecionar todos os elementos
        mode3_frame = ttk.Frame(modes_frame)
        mode3_frame.pack(fill=tk.X)
        
        mode3_title = ttk.Label(mode3_frame, text="Tudo", 
                               font=("Arial", 13, "bold"), foreground="#f57c00")
        mode3_title.pack(anchor=tk.W)
        
        text_modo_tudo = """1. Utilize o Atalho Ctrl+A para selecionar todos os elementos
2. Utilize o Atalho Ctrl+C ou vá em 'Configurações' -> 'Edição' -> 'Copiar'
3. Caso necessário, o Praixs possui a opção de 'Recortar', localizada entre as funções de 'Copiar' e 'Colar'
4. Selecione a célula destino, onde você quer colar
5. Utilize o Atalho Ctrl+V ou vá em 'Configurações' -> 'Edição' -> 'Colar'
"""

        mode3_desc = ttk.Label(mode3_frame, 
                              text=text_modo_tudo,
                              font=("Arial", 10), wraplength=550, justify=tk.LEFT)
        mode3_desc.pack(anchor=tk.W, padx=(20, 0), pady=(5, 0))

    def _show_help_row_column_ops(self):
        """Mostra ajuda sobre as formas de utilizar as operações com colunas"""        
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Título principal
        title_label = ttk.Label(content_frame, text="Operações de Linha/Coluna", 
                            font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 20))
        
        # Descrição do processo
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))
        
        desc_text = """O Praxis possui funções específicas para operações com linhas e colunas no layout do Trackplan. Essas operações facilitam a manipulação de grandes áreas do layout, permitindo adicionar, remover ou modificar linhas e colunas inteiras de uma só vez.
Tais opções podem ser acessadas clicando com o botão direito na coluna/linha que deseja ver as opções."""

        desc_label = ttk.Label(desc_frame, text=desc_text, 
                            font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)

        operacoes_text =['As operações disponíveis incluem:',
'• Adicionar Linha/Coluna: Insere uma nova linha ou coluna no layout',
'• Remover Linha/Coluna: Exclui uma linha ou coluna existente do layout',
'• Copiar ou Recortar Linha/Coluna: Permite copiar ou recortar uma linha ou coluna inteira para colar em outro local',
'• Colar Linha/Coluna: Cola a linha ou coluna copiada ou recortada em outro local do layout']

        operacoes_disponiveis = ttk.LabelFrame(content_frame, text="Operações Disponíveis", padding="15")
        operacoes_disponiveis.pack(fill=tk.X, pady=(0,20))
        for step in operacoes_text:
            ttk.Label(operacoes_disponiveis, text=step, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)

    def _show_help_element_highlighting(self):
        """Mostra ajuda sobre o destacamento de elementos no Trackplan"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Título principal
        title_label = ttk.Label(content_frame, text="Destacamento de Elementos", 
                               font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 20))

        # Descrição do processo
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))

        desc_text = """O Praxis possui a funcionalidade de destacar elementos no Trackplan. Essa funcionalidade se dá devido a FMA.
A FMA assegura uma área, que é delimitada por sensores, para demarcar essa área, é necessário adicionar os elementos que compõem a mesma. Tais elementos podem ser destacados em azul, simulando a opção real do FDS.
Para entender mais sobre as FMAs, visite a aba de ajuda da FMA em 'Designer Trackplan' -> 'Ferramentas' -> 'FMAs'."""
        
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)
        
        howto_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="10")
        howto_frame.pack(fill=tk.X, pady=(0, 20))
        howto_text = ["1. Selecione a ferramenta 'Selecionar' na barra de ferramentas",
    "2. Selecione a FMA que você quer destacar",
    "3. Utilize o atalho Ctrl + F ou vá em 'Configurações' -> 'Edição' -> 'Editar FMA'",
    "4. Verfique nas abas 'Sensores associados' e 'Trilhos Associados', caso esteja vazia, adicione elementos.", 
    "5. Selecione a opção 'Testar FMA (Destacar Limites)'",
    "6. Verifique se os elementos destacados estão corretos"]
            
        for step in howto_text:
            ttk.Label(howto_frame, text=step, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)

    def _show_help_common_errors(self):
        """Mostra ajuda sobre erros comuns que podem ocorrer"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Título principal
        title_label = ttk.Label(content_frame, text="Erros Comuns", 
                               font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 20))

        # Descrição do processo
        desc_frame = ttk.LabelFrame(content_frame, text="Problema/Solução", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))

        desc_text = """O Praxis ainda está em fase de desenvolvimento, portanto alguns erros e bugs podem ocorrer durante o processo de trabalho. """
        
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)

    def _show_help_area_selection(self):
        """Mostra ajuda sobre a seleção em área no trackplan"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Título principal
        title_label = ttk.Label(content_frame, text="Seleção em Área", 
                               font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 20))

        # Descrição do processo
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))

        desc_text = """O Praxis abriga possui a ferramenta de seleção em área, que pode tanto ser feita utilizando o Ctrl+Clique esquerdo em cada elemento que será selcionado.
Ou utilizando o atalho de seleção em bloco, Ctrl + Shift. O primeiro clique com o atalho pressionado marca o início da área de seleção, e o segundo clique marca o fim da área de seleção, formnando sempre um retângulo."""
        
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)

        howto_frame = ttk.LabelFrame(content_frame, text="Como Usar", padding="10")
        howto_frame.pack(fill=tk.X, pady=(0, 20))
        howto_text = ["1. Selecione a ferramenta 'Selecionar' na barra de ferramentas",
    "2. Com o atalho Ctrl+Shift pressionado, clique com o botão esquerdo no espaço superior mais a esquerda da área que deseja selecionar",
    "3. Com o atalho ainda pressionado, clique com o botão esquerdo no espaço inferior mais a direita da área que deseja selecionar",
    "4. Solte o atalho Ctrl+Shift",
    "5. Todos os elementos dentro da área selecionada estarão agora selecionados e prontos para ações como recortar, copiar ou deletar."]
            
        for step in howto_text:
            ttk.Label(howto_frame, text=step, font=("Arial", 10), justify="left").pack(anchor="w", pady=2)

    def _show_help_load_save_trackplan(self):
        """Mostra ajuda sobre salvar/carregar arquivos XML"""
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Título principal
        title_label = ttk.Label(content_frame, text="Carregar/Salvar", 
                               font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 20))
        
        # Descrição do processo
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))
        
        desc_text = """O Praxis possui a funcionalide de carregar ou salvar os arquivos Trackplan.xml na aba Designer Trackplan. Permitindo salvar os arquivos para editar posteriormente, ou acrescentar informação a um antigo layout."""
        
        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)
        
        # Arquivos necessários
        files_frame = ttk.LabelFrame(content_frame, text="Carregar Trackplan", padding="15")
        files_frame.pack(fill=tk.X, pady=(0, 20))
        
        files_list = [
            "1. Utilize o atalho Ctrl+O ou vá em Configurações -> Edição -> Carregar Trackplan.",
            "2. Localize um arquivo Trackplan.xml válido.", 
            "3. Aguarde os itens serem carregados no Trackplan.",
            "4. Inicie o fluxo de trabalho."
        ]
        
        for file_item in files_list:
            file_label = ttk.Label(files_frame, text=file_item, 
                                  font=("Arial", 10), wraplength=550, justify=tk.LEFT)
            file_label.pack(anchor=tk.W, pady=2)
        
        # Passo a passo
        steps_frame = ttk.LabelFrame(content_frame, text="Salvar Trackplan", padding="15")
        steps_frame.pack(fill=tk.X, pady=(0, 20))
        
        steps = [
            "1. Para salvar o seu layout do Trackplan, utilize o atalho Ctrl+B ou vá em Configurações -> Edição -> Salvar Trackplan.",
            "2. Selecione um diretório para salvar o arquivo Trackplan.xml",
            "3. Espere a confirmação de sucesso."
        ]
        
        for i, step in enumerate(steps, 1):
            step_frame = ttk.Frame(steps_frame)
            step_frame.pack(fill=tk.X, pady=2)
            
            step_label = ttk.Label(step_frame, text=step, 
                                  font=("Arial", 10), wraplength=520, justify=tk.LEFT)
            step_label.pack(anchor=tk.W)
        
        # Avisos importantes
        warnings_frame = ttk.LabelFrame(content_frame, text="⚠️ Avisos Importantes", padding="15")
        warnings_frame.pack(fill=tk.X)
        
        warnings = [
            "• O salvamento do Trackplan.xml salva também os cubículos, caso não estejam configurados ainda o código pode não funcionar corretamente.",
            "• Carregar e editar um Trackplan não altera o arquivo, é necessário salvar no mesmo diretório, substituindo os arquivos.",
            "• Para salvar e utilizar o programa criado, utilize sempre a aba de visualização XML.",
            "• Desenvolva o hábito de testar o programa utilizando o 'Validador' na aba Visualização XML.",
            "• Sempre faça backup dos arquivos originais antes de aplicar alterações.",
        ]
        
        for warning in warnings:
            warning_label = ttk.Label(warnings_frame, text=warning, 
                                    font=("Arial", 10), wraplength=550, justify=tk.LEFT, foreground="#d32f2f")
            warning_label.pack(anchor=tk.W, pady=2)

    def _show_help_xml_elements_reference(self):
        """Mostra ajuda sobre arquivos XML """
        content_frame = ttk.Frame(self.help_content_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        #Título principal
        title_label = ttk.Label(content_frame, text="Elementos XML",
                                font=("Arial", 16, "bold"), foreground="#0078d4")
        title_label.pack(anchor=tk.W, pady=(0, 20))

        #Descrição
        desc_frame = ttk.LabelFrame(content_frame, text="Descrição", padding="15")
        desc_frame.pack(fill=tk.X, pady=(0, 20))

        desc_text = """Abaixo veremos uma explicação de como os dados inseridos nos campos durante o processo de criação do Praxis são distribuídos nos arquivos XML. Veremos também explicações para entender ambos códigos XML."""

        desc_label = ttk.Label(desc_frame, text=desc_text, 
                              font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        desc_label.pack(anchor=tk.W)
        
        # FdsConfig
        fdsconfig_frame = ttk.LabelFrame(content_frame, text="FdsConfig.xml", padding="15")
        fdsconfig_frame.pack(fill=tk.X, pady=(0, 20))

        fdsconfig_text = """O arquivo FdsConfig.xml é completamente programado na aba 'Configuração FDS', onde é definido nome, as configurações de rede e os elementos do sistema.
Aparecendo no cabeçalho do arquivo FdsConfig.xml, é possível ver onde nossas configurações de rede e nomes estão sendo utilizadas. 
Logo abaixo, dentro da marcação '<ElementList>' é possível identificar a lista de elementos que cadastramos no FdsConfig.xml, onde é atribuído o seu Id, tipo de elemento, nome de atribuição e o Id que será utilizado para referências.
Tal processo é repetido para cada elemento."""

        fdsconfig_label = ttk.Label(fdsconfig_frame, text=fdsconfig_text,
                                    font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        fdsconfig_label.pack(anchor=tk.W)

        # Trackplan
        trackplan_frame = ttk.LabelFrame(content_frame, text="Trackplan.xml", padding="15")
        trackplan_frame.pack(fill=tk.X, pady=(0, 20))

        trackplan_text = """Para a criação do Trackplan por inteiro, é necessário passar por duas etapas: O design do layout do Trackplan feito na aba Designer Trackplan e os cubículos que são desenvolvidos na aba 'Cubículos'.
Primeiramente, trataremos do Designer Trackplan. O arquivo começa com um cabeçalho com alguns detalhes sobre o nome e algumas configurações de rede, que devem ser coniventes com as inseridas no arquivo FdsConfig.xml do mesmo projeto.
Logo abaixo, dentro da marcação '<Track>', onde é dimensionado o canvas, é adicionado os elementos que compuseram o layout, como: Trilhos, Chaves, Links, Sensores e FMAs. Cada elemento possui um Id, ângulo, mirror (se tiver) e suas coordenadas no layout.
Após o término do layout marcado pelo fechamento da marcação '</Track>', é iniciado a seção de cubículos, dentro da marcação '<Cubicles>'. Cada cubículo é adicionado com suas propriedades por meio do marcador '<Cubicle>', como Id, nome e onde são cadastrados cada componente."""

        trackplan_label = ttk.Label(trackplan_frame, text=trackplan_text,
                                    font=("Arial", 11), wraplength=600, justify=tk.LEFT)
        trackplan_label.pack(anchor=tk.W)

    def change_fds_model(self):
        """Permite trocar o modo FDS durante a execução"""
        # Verificar se há alterações não validadas
        if getattr(self, "changes_since_validation", False):
            response = messagebox.askyesnocancel(
                "Trocar Modo FDS",
                "Existem alterações não salvas/validadas.\n\n"
                "Deseja salvar antes de trocar de modo?\n\n"
                "Sim = Salvar e continuar\n"
                "Não = Descartar e continuar\n"
                "Cancelar = Não trocar modo"
            )
            
            if response is None:  # Cancelar
                return
            elif response:  # Sim - Salvar
                # Tentar salvar via botão de visualização XML
                try:
                    self.save_trackplan()
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao salvar: {e}")
                    return
        
        # Escolher novo modo
        dialog = FDSModelSelectorDialog(self.root, current_model=self.fds_model, show_remember=True)
        new_model, remember = dialog.show()
        if not new_model or new_model == self.fds_model:
            return

        # Opção de apagar tudo ou manter (avisando perdas 102->101)
        clear_data = False
        if self.fds_model == "FDS102" and new_model == "FDS101":
            clear_data = messagebox.askyesno(
                "Trocar para FDS101",
                "Você está mudando de FDS102 para FDS101.\n"
                "Isso pode causar perda de valores específicos do FDS102 (ex.: Default Gateway).\n\n"
                "Deseja APAGAR os dados do projeto e começar limpo?"
            )
        else:
            clear_data = messagebox.askyesno(
                "Trocar Modo FDS",
                "Você está mudando de FDS101 para FDS102.\n"
                "Deseja APAGAR os dados do projeto ao trocar o modo?"
            )

        if clear_data:
            # Limpeza mínima, sem reiniciar
            try:
                if hasattr(self, "clear_trackplan"):
                    # evita prompts duplicados se sua função já pergunta
                    # (se quiser 100% sem prompts, posso criar um método interno 'silent')
                    self.clear_trackplan()
            except Exception as e:
                print(f"Limpeza trackplan falhou: {e}")

            try:
                if hasattr(self, "clear_all_cubicles"):
                    self.clear_all_cubicles()
            except Exception as e:
                print(f"Limpeza cubicles falhou: {e}")

            try:
                if hasattr(self, "clear_all_elements"):
                    self.clear_all_elements()
            except Exception as e:
                print(f"Limpeza elementos falhou: {e}")

        # Aplicar modo e atualizar UI sem reiniciar
        self.apply_fds_model(new_model, remember=remember)

def main():
    """Função principal"""
    root = tk.Tk()
    root.title("Praxis")
    
    # Carregar configuração do usuário
    config = load_user_config()
    fds_model = config.get('fds_model', 'FDS101')
    remember = config.get('remember', False)
    
    # Se não deve lembrar, ou se é primeira execução, mostrar diálogo
    if not remember:
        root.withdraw()  # Ocultar janela principal temporariamente
        dialog = FDSModelSelectorDialog(root, current_model=fds_model, show_remember=True)
        selected_model, remember_choice = dialog.show()
        
        if selected_model:
            fds_model = selected_model
            # Salvar preferência
            save_user_config(fds_model, remember_choice)
        else:
            # Usuário cancelou - usar padrão FDS101
            fds_model = 'FDS101'
        
    root.deiconify()  # Mostrar janela principal
    
    # Criar aplicação com o modelo selecionado
    app = FDSFormGenerator(root, fds_model=fds_model)
    root.mainloop()

if __name__ == "__main__":
    main()
