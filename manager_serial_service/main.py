from __future__ import annotations
from typing import Dict
from abstract.factory.concrete_factory_win import WindownsAppComponents
from abstract.factory.concrete_factory_linux import LinuxAppComponents
from abstract.factory.abstract_factory import AppComponents
import platform
import sys
import json
import threading
import time
from utils.logger import Logger
from constant import (BROKER, PORT, POLL_SERIAL, POLL_REGISTER_SUB, StructMsg, CLIENT_ID,
                      TOPIC_DEVICE, TOPIC_DEVICE_STT, TOPIC_INFO, TOPIC_CHECK_INFO)

class RFIDVideoApp:
    def __init__(self, app_components: AppComponents) -> None:
        # 1) Hạ tầng theo nền tảng
        self.__is_registered = False

        # 2) Serial + Media (theo Abstract Factory)
        self.__serial = app_components.create_serial()
        self.__mqtt_client = app_components.create_mqtt_client(BROKER, PORT)

        # 3) Trạng thái chống lặp
        self.__last_cmd: str | None = None

        # 4) Vòng lặp đọc serial + UI loop
        thread = threading.Thread(target=self.__register_topic_sub, daemon=True)
        thread.start()
    
    def close_connect(self):
        self.__serial.close()
        self.__mqtt_client.disconnect()

    # Serial
    def poll_serial(self) -> None:
        while True:
            lines = self.__serial.receive_datas()
            for item in lines:
                if item.get(StructMsg.CMD) == StructMsg.FEEDBACK:
                    self.__mqtt_client.publisher(TOPIC_DEVICE_STT, item)

                elif item.get(StructMsg.CMD) == StructMsg.INFO:
                    info = {
                        "cmd": "info",
                        "msg": {
                            "serial_number": CLIENT_ID,
                            "data": item.get("data")
                        }
                    }
                    self.__mqtt_client.publisher(TOPIC_INFO, info)

            time.sleep(POLL_SERIAL)
            
    # Xử lý lệnh từ pc server
    def __register_topic_sub(self):
        while not self.__is_registered:
            if self.__mqtt_client.is_connected():
                
                self.__mqtt_client.subscriber(TOPIC_CHECK_INFO, self.__handel_topic_check_info)
                self.__mqtt_client.subscriber(TOPIC_DEVICE, self.__handel_topic_device)
                self.__is_registered = True

            time.sleep(POLL_REGISTER_SUB)


    def __handel_topic_device(self, msg: Dict) -> None:
        """
        {
            "cmd": "io",
            "data": {
                    "D1": 1,
                }
            }

            "cmd": "io",
            "data": {
                    "D2": 0,
                }
            }

            "cmd": "io",
            "data": {
                    "D3": 1
                }
            }

            "cmd": "status",
            "msg": null
             
            "cmd": "reset"
            "data": null

            "cmd": "info"
            "data": null

            "cmd": "blink"
            "data": {
                    "io": "D1",
                    "duration": 1000
                }
            }
        """
        self.__serial.add_data_send(msg)

    def __handel_topic_check_info(self, msg: Dict) -> None:
        """
            msg = {
                "cmd": "check_info",
                "msg": {
                    "type": "serial"
                }
            }

            {
                "cmd":"info",
                "data":{
                    "name":"esp32_devkit_v1",
                    "input":["D18", "D19", "A34"],
                    "output":["D2","D12","D13","D14","D15","D27"]
                }
            }
        """
        print(msg)
        msg_rc = msg.get("msg")
        if msg_rc.get("type") == "serial":
            self.__serial.add_data_send({"cmd":"info","data":None})


def choose_factory() -> AppComponents:
    if platform.system() == "Linux":
        return LinuxAppComponents()
    elif platform.system() == "Windows":
        return WindownsAppComponents()
    else:
        Logger().info("System don't support")
        sys.exit(1)

if __name__ == "__main__":
    Logger(level='warn', to_screen=False, to_file=True)
    try:
        app_components = choose_factory()
        rfid = RFIDVideoApp(app_components)
        rfid.poll_serial()
    except KeyboardInterrupt:
        rfid.close_connect()
        print("EXIT")
    except Exception as e:
        rfid.close_connect()
        Logger().critical("Fatal error: %s", e, exc_info=True)
        sys.exit(1)
