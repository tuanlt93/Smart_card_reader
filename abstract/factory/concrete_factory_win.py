from .abstract_factory import AppComponents
from ..product.abstract_product import Config, SerialPort, MediaEngine, MqttClient
from ..product.concrete_products_win import WindownsConfig, WindownsSerialPort, WindownsVLCMediaEngine, WindownsMqttClient
from pathlib import Path
from typing import Dict, List

class WindownsAppComponents(AppComponents):
    def create_config(self) -> Config:
        return WindownsConfig()

    def create_serial(self) -> SerialPort:
        return WindownsSerialPort()
    
    def create_mqtt_client(self, broker: str, port: int) -> MqttClient:
        return WindownsMqttClient(broker = broker, port = port)

    def create_media(self, uid_map: Dict[str, str], serial_port: SerialPort, mqtt_client: MqttClient) -> MediaEngine:
        return WindownsVLCMediaEngine(uid_map, serial_port, mqtt_client)