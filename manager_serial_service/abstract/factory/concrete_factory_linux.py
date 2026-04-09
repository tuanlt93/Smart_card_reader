from .abstract_factory import AppComponents
from ..product.abstract_product import SerialPort, MqttClient
from ..product.concrete_products_linux import LinuxSerialPort, LinuxMqttClient
from pathlib import Path
from typing import Dict

class LinuxAppComponents(AppComponents):

    def create_serial(self) -> SerialPort:
        return LinuxSerialPort()
    
    def create_mqtt_client(self, broker: str, port: int) -> MqttClient:
        return LinuxMqttClient(broker = broker, port = port)