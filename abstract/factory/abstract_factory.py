from abc import ABC, abstractmethod
from ..product.abstract_product import Config, SerialPort, MediaEngine, MqttClient
from pathlib import Path
from typing import Dict, List
# ──────────────────────────────────────────────────────────────
# Abstract Factory
# ──────────────────────────────────────────────────────────────

class AppComponents(ABC):
    @abstractmethod
    def create_config(self) -> Config: ...

    @abstractmethod
    def create_serial(self) -> SerialPort: ...

    @abstractmethod
    def create_mqtt_client(self, broker: str, port: int) -> MqttClient: ...

    @abstractmethod
    def create_media(self, uid_map: Dict[str, str], serial_port: SerialPort, mqtt_client: MqttClient) -> MediaEngine: ...
        
