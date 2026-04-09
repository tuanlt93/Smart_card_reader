from .abstract_factory import AppComponents
from ..product.abstract_product import Config, MediaEngine, MqttClient
from ..product.concrete_products_linux import LinuxConfig, LinuxVLCMediaEngine, LinuxMqttClient
from pathlib import Path
from typing import Dict

class LinuxAppComponents(AppComponents):
    def create_config(self) -> Config:
        return LinuxConfig()
    
    def create_mqtt_client(self, broker: str, port: int) -> MqttClient:
        return LinuxMqttClient(broker = broker, port = port)

    def create_media(self, uid_map: Dict[str, str], mqtt_client: MqttClient) -> MediaEngine:
        return LinuxVLCMediaEngine(uid_map, mqtt_client)