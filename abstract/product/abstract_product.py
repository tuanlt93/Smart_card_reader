from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Dict, Callable
import tkinter
from PIL import Image, ImageTk

# --- Abstract Products ---

class Config(ABC):
    @abstractmethod
    def home_img(self) -> Path: ...

    @abstractmethod
    def load_config(self) -> Dict[str, str]: ...

    @abstractmethod
    def serial_port_name(self) -> str: ...

    @abstractmethod
    def baudrate(self) -> int: ...


class SerialPort(ABC):
    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def receive_datas(self) -> List[str]: ...

    @abstractmethod
    def is_opened(self) -> bool: ...

    @abstractmethod
    def get_time_polling(self) -> int: ...


class MediaEngine(ABC):
    @abstractmethod
    def show_home(self) -> None: ...

    @abstractmethod
    def play_video(self, uid: str) -> None: ...

    @abstractmethod
    def mainloop(self) -> None: ...
    
    @abstractmethod
    def run_loop_after_time(self, poll_time_ms: int, func: Callable) -> None: ...

    @abstractmethod
    def cancel_run_loop_after_time(self, job: str) -> None: ...











