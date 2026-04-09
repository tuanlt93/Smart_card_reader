from __future__ import annotations
from typing import Dict
from abstract.factory.concrete_factory_win import WindownsAppComponents
from abstract.factory.concrete_factory_linux import LinuxAppComponents
from abstract.factory.abstract_factory import AppComponents
import platform
import sys
import json
from utils.logger import Logger
from constant import (BROKER, PORT, POLL_REGISTER_SUB, MediaState, StructMsg,
                      EXPORT_DISPLAY, TOPIC_CHECK_INFO, TOPIC_INFO, CLIENT_ID,
                      TOPIC_VIDEO, TOPIC_VIDEO_STT)

class RFIDVideoApp:
    def __init__(self, app_components: AppComponents) -> None:
        # 1) Hạ tầng theo nền tảng
        self.__config = app_components.create_config()        # int
        self.__uid_map: Dict[str, str] = self.__config.load_config()  # {uid: filepath}

        # 2)  Media (theo Abstract Factory)
        self.__mqtt_client = app_components.create_mqtt_client(BROKER, PORT)
        self.__media  = app_components.create_media(self.__uid_map, self.__mqtt_client)

        # 3) Trạng thái chống lặp

        # 4) Vòng lặp đọc serial + UI loop
        self.__run_register_sub = ""

        self.__run_register_sub = self.__media.run_loop_after_time(POLL_REGISTER_SUB, self.__register_topic_sub)
        self.__media.mainloop()

            
    # Xử lý lệnh từ pc server
    def __register_topic_sub(self):
        if self.__mqtt_client.is_connected():
            self.__mqtt_client.subscriber(TOPIC_CHECK_INFO, self.__handel_topic_check_info)
            if EXPORT_DISPLAY:
                self.__mqtt_client.subscriber(TOPIC_VIDEO, self.__handel_topic_video)
            if self.__run_register_sub:
                self.__media.cancel_run_loop_after_time(self.__run_register_sub)
                self.__run_register_sub = ""
        else:
            self.__run_register_sub = self.__media.run_loop_after_time(POLL_REGISTER_SUB, self.__register_topic_sub)

    def __handel_topic_check_info(self, msg: Dict) -> None:
        """
            msg = {
                "cmd": "check_info",
                "msg": {
                    "type": "media"
                }
            }
        """
        
        msg_rc = msg.get("msg")
        if msg_rc.get("type") == "media":
            print(msg)
            info = {
                "cmd": "info",
                "msg": {
                    "serial_number": CLIENT_ID,
                    "data": self.__uid_map
                }
            }
            self.__mqtt_client.publisher(TOPIC_INFO, info)

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
