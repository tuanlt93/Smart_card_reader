from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Dict, Callable
import tkinter
import json
from PIL import Image, ImageTk
# --- Abstract Products ---

class Config(ABC):
    @abstractmethod
    def load_config(self) -> Dict[str, str]: ...

class SerialPort(ABC):
    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def receive_datas(self) -> List: ...

    @abstractmethod
    def add_data_send(self, data: Dict) -> None: ...

    @abstractmethod
    def is_opened(self) -> bool: ...

class MqttClient(ABC):
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def publisher(self, topic: str, payload: Dict, retain: bool = False) -> None: ...

    @abstractmethod
    def subscriber(self, topic: str, callback: Callable, *args, **kwargs): ...

    @abstractmethod
    def disconnect(self) -> None: ...

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











