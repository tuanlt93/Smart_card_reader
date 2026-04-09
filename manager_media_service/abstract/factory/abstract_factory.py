from abc import ABC, abstractmethod
from ..product.abstract_product import Config, MediaEngine, MqttClient
from pathlib import Path
from typing import Dict, List
# ──────────────────────────────────────────────────────────────
# Abstract Factory
# ──────────────────────────────────────────────────────────────

class AppComponents(ABC):
    @abstractmethod
    def create_config(self) -> Config: ...

    @abstractmethod
    def create_mqtt_client(self, broker: str, port: int) -> MqttClient: ...

    @abstractmethod
    def create_media(self, uid_map: Dict[str, str], mqtt_client: MqttClient) -> MediaEngine: ...
        
