from __future__ import annotations
from typing import Dict
from abstract.factory.concrete_factory_win import WindownsAppComponents
from abstract.factory.concrete_factory_linux import LinuxAppComponents
from abstract.factory.abstract_factory import AppComponents
import platform
import sys
import json
from utils.logger import Logger
from constant import (BROKER, PORT, POLL_SERIAL_MS, POLL_REGISTER_SUB, MediaState, StructMsg,
                      TOPIC_DEVICE, TOPIC_DEVICE_STT, EXPORT_DISPLAY,
                      TOPIC_VIDEO, TOPIC_VIDEO_STT)

class RFIDVideoApp:
    def __init__(self, app_components: AppComponents) -> None:
        # 1) Hạ tầng theo nền tảng
        self.__config = app_components.create_config()        # int
        self.__uid_map: Dict[str, str] = self.__config.load_config()  # {uid: filepath}

        # 2) Serial + Media (theo Abstract Factory)
        self.__serial = app_components.create_serial()
        self.__mqtt_client = app_components.create_mqtt_client(BROKER, PORT)
        self.__media  = app_components.create_media(self.__uid_map, self.__serial, self.__mqtt_client)

        # 3) Trạng thái chống lặp
        self.__last_cmd: str | None = None

        # 4) Vòng lặp đọc serial + UI loop
        self.__run_poll_serial  = ""
        self.__run_register_sub = ""

        self.__run_poll_serial = self.__media.run_loop_after_time(POLL_SERIAL_MS, self.__poll_serial)
        self.__run_register_sub = self.__media.run_loop_after_time(POLL_REGISTER_SUB, self.__register_topic_sub)
        self.__media.mainloop()

    # Serial
    def __poll_serial(self) -> None:
        lines = self.__serial.receive_datas()
        for item in lines:
            item[StructMsg.CMD] = StructMsg.FEEDBACK
            self.__mqtt_client.publisher(TOPIC_DEVICE_STT, item)
        self.__run_poll_serial = self.__media.run_loop_after_time(POLL_SERIAL_MS, self.__poll_serial)
            
    # Xử lý lệnh từ pc server
    def __register_topic_sub(self):
        if self.__mqtt_client.is_connected():
            self.__mqtt_client.subscriber(TOPIC_DEVICE, self.__handel_topic_device)
            if EXPORT_DISPLAY:
                self.__mqtt_client.subscriber(TOPIC_VIDEO, self.__handel_topic_video)
            if self.__run_register_sub:
                self.__media.cancel_run_loop_after_time(self.__run_register_sub)
                self.__run_register_sub = ""
        else:
            self.__run_register_sub = self.__media.run_loop_after_time(POLL_REGISTER_SUB, self.__register_topic_sub)

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

    def __handel_topic_video(self, msg: Dict) -> None:
        """{
            "cmd": "play", / "stop"
            "data": "001"
        """
        cmd = msg.get(StructMsg.CMD)
        uid_video = msg.get(StructMsg.DATA)

        if cmd == MediaState.PLAY:
            self.__media.play_video(uid_video)
        elif cmd == MediaState.STOP:
            self.__media.show_home()

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
        RFIDVideoApp(app_components)
    except Exception as e:
        Logger().critical("Fatal error: %s", e, exc_info=True)
        sys.exit(1)
