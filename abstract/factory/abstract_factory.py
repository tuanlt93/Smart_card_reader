from abc import ABC, abstractmethod
from ..product.abstract_product import Config, SerialPort, MediaEngine
from pathlib import Path
from typing import Dict
# ──────────────────────────────────────────────────────────────
# Abstract Factory
# ──────────────────────────────────────────────────────────────

class AppComponents(ABC):
    @abstractmethod
    def create_config(self) -> Config: ...

    @abstractmethod
    def create_serial(self, port_name: str, baudrate: int) -> SerialPort: ...

    @abstractmethod
    def create_media(self, home_img_path: Path, uid_map: Dict[str, str], serial_port: SerialPort) -> MediaEngine: ...
        
