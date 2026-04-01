import uuid
import platform
from pathlib import Path

def get_client_id() -> str:
    # Lấy địa chỉ MAC dưới dạng số nguyên, sau đó chuyển sang hex
    node = uuid.getnode()
    mac_hex = hex(node)[2:] 
    return f"python_{platform.system().lower()}_{mac_hex}"

def get_flatform() -> str:
    if platform.system() == "Linux":
        return "Linux"
    elif platform.system() == "Windows":
        return "Windows"
    else:
        return "None"
    
def get_serial() -> str:
    if platform.system() == "Linux":
        return "/dev/device0"
    elif platform.system() == "Windows":
        return "COM20"
    else:
        return "None"

class MediaState:
    PLAY = "play"
    STOP = "stop"
    PLAYING = "playing"
    STOPED  = "stoped"

class StructMsg:
    CMD = "cmd"
    DATA = "data"
    FEEDBACK = "feedback"

# Main
PLATFORM_SYSTEM = get_flatform()
EXPORT_DISPLAY = True

# Serial
SERIAL_PORT = "/dev/device0" if PLATFORM_SYSTEM == "Linux" else "COM20"
BAURATE = 115200
MAX_BACKOFF = 5
MIN_BACKOFF = 1
POLL_SERIAL_MS = 100

# Media
VIDEO_DIR = Path(r"/home/tuanlt/Videos") if PLATFORM_SYSTEM == "Linux" else Path(r"D:\Outsource\RFID\Video")
HOME_PATH = Path(r"D:\Outsource\RFID\JPG\Home.jpg")
CFG_PATH = Path(r"config.yaml")

# Mqtt
BROKER = "192.168.137.192"
PORT = 1883
TOPIC_DEVICE = "/topic/device"
TOPIC_DEVICE_STT = "/topic/device/status"
TOPIC_VIDEO = "/topic/video"
TOPIC_VIDEO_STT = "/topic/video/status"
USENAME = "admin"
PASSWORD = "admin"
CLIENT_ID = get_client_id()
POLL_REGISTER_SUB = 2000

