from .abstract_factory import AppComponents
from ..product.abstract_product import Config, SerialPort, MediaEngine
from ..product.concrete_products_linux import LinuxConfig, LinuxSerialPort, LinuxVLCMediaEngine
from pathlib import Path
from typing import Dict

class LinuxAppComponents(AppComponents):
    def create_config(self) -> Config:
        return LinuxConfig()

    def create_serial(self, port_name: str = "/dev/rfid0", baudrate: int = 115200) -> SerialPort:
        return LinuxSerialPort(port_name = port_name, baudrate = baudrate)

    def create_media(self, home_img_path: Path, uid_map: Dict[str, str], serial_port: SerialPort) -> MediaEngine:
        return LinuxVLCMediaEngine(home_img_path = home_img_path, uid_map = uid_map, serial_port = serial_port)