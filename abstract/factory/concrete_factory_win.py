from .abstract_factory import AppComponents
from ..product.abstract_product import Config, SerialPort, MediaEngine
from ..product.concrete_products_win import WindownsConfig, WindownsSerialPort, WindownsVLCMediaEngine
from pathlib import Path
from typing import Dict

class WindownsAppComponents(AppComponents):
    def create_config(self) -> Config:
        return WindownsConfig()

    def create_serial(self, port_name: str = "COM20", baudrate: int = 115200) -> SerialPort:
        return WindownsSerialPort(port_name = port_name, baudrate = baudrate)

    def create_media(self, home_img_path: Path, uid_map: Dict[str, str], serial_port: SerialPort) -> MediaEngine:
        return WindownsVLCMediaEngine(home_img_path = home_img_path, uid_map = uid_map, serial_port = serial_port)