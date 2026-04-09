from .abstract_factory import AppComponents
from ..product.abstract_product import SerialPort, MqttClient
from ..product.concrete_products_win import WindownsSerialPort, WindownsMqttClient
from pathlib import Path
from typing import Dict, List

class WindownsAppComponents(AppComponents):
    
    def create_serial(self) -> SerialPort:
        return WindownsSerialPort()
    
    def create_mqtt_client(self, broker: str, port: int) -> MqttClient:
        return WindownsMqttClient(broker = broker, port = port)