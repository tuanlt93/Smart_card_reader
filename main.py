from __future__ import annotations
from typing import Dict
from abstract.factory.concrete_factory_win import WindownsAppComponents
from abstract.factory.concrete_factory_linux import LinuxAppComponents
from abstract.factory.abstract_factory import AppComponents
import platform
import sys
from utils.logger import Logger

POLL_MS = 200

class RFIDVideoApp:
    def __init__(self, app_components: "AppComponents") -> None:
        # 1) Hạ tầng theo nền tảng
        self.__config            = app_components.create_config()
        self.__home_img_path     = self.__config.home_img()           # Path
        self.__serial_port_name  = self.__config.serial_port_name()   # str
        self.__baudrate          = self.__config.baudrate()           # int
        self.__uid_map: Dict[str, str] = self.__config.load_config()  # {uid: filepath}

        # 2) Serial + Media (theo Abstract Factory)
        self.__serial = app_components.create_serial(self.__serial_port_name, self.__baudrate)
        self.__media  = app_components.create_media(self.__home_img_path, self.__uid_map, self.__serial)

        # 3) Trạng thái chống lặp
        self.__last_cmd: str | None = None

        # 4) Vòng lặp đọc serial + UI loop
        self.__run_poll_serial  = ""
        self.__run_reconnect    = ""
        self.__run_poll_serial = self.__media.run_loop_after_time(POLL_MS, self.__poll_serial)
        self.__media.mainloop()

    # ── Serial ────────────────────────────────────────────────
    def __poll_serial(self) -> None:
        if self.__serial.is_opened():
            lines = self.__serial.receive_datas()
            if lines:
                self.__process_cmd(lines[-1])
            
            self.__run_poll_serial = self.__media.run_loop_after_time(POLL_MS, self.__poll_serial)
        else:
            # Hủy loop poll serial
            self.__media.cancel_run_loop_after_time(self.__run_poll_serial)
            self.__run_poll_serial  = ""

            # Run loop reconnect
            self.__run_reconnect = self.__media.run_loop_after_time(self.__serial.get_time_polling() * 1000, self.__reconnect_serial)
            

    def __reconnect_serial(self) -> None:
        self.__serial.open()
        if self.__serial.is_opened():
            # Hủy loop reconnect
            self.__media.cancel_run_loop_after_time(self.__run_reconnect)
            self.__run_reconnect    = ""

            # Run loop poll serial
            self.__run_poll_serial = self.__media.run_loop_after_time(POLL_MS, self.__poll_serial)
        else:
            self.__run_reconnect = self.__media.run_loop_after_time(self.__serial.get_time_polling() * 1000, self.__reconnect_serial)


    # ── Xử lý lệnh từ ESP32 ───────────────────────────────────
    def __process_cmd(self, cmd: str) -> None:
        if cmd == self.__last_cmd:
            return  # chống lặp y hệt, tránh spam phát lại

        if cmd == "removed":
            self.__media.show_home()
        elif cmd in self.__uid_map:
            self.__media.play_video(cmd)
        else:
            Logger().warning("Unknown UID/cmd: %s", cmd)

        self.__last_cmd = cmd


def choose_factory() -> "AppComponents":
    if platform.system() == "Linux":
        return LinuxAppComponents()
    elif platform.system() == "Windows":
        return WindownsAppComponents()
    else:
        Logger().info("System don't support")
        sys.exit(1)

if __name__ == "__main__":
    try:
        app_components = choose_factory()
        RFIDVideoApp(app_components)
    except Exception as e:
        Logger().critical("Fatal error: %s", e, exc_info=True)
        sys.exit(1)
