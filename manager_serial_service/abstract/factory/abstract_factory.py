from abc import ABC, abstractmethod
from ..product.abstract_product import SerialPort, MqttClient
from pathlib import Path
from typing import Dict, List
# ──────────────────────────────────────────────────────────────
# Abstract Factory
# ──────────────────────────────────────────────────────────────

class AppComponents(ABC):
    @abstractmethod
    def create_serial(self) -> SerialPort: ...

    @abstractmethod
    def create_mqtt_client(self, broker: str, port: int) -> MqttClient: ...
        
