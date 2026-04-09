import platform
from pathlib import Path
import subprocess

def get_flatform() -> str:
    if platform.system() == "Linux":
        return "Linux"
    elif platform.system() == "Windows":
        return "Windows"
    else:
        return "None"
    
def get_device_id():
    
    if get_flatform() == "Linux":
        # Code lấy serial cho Pi như đã viết ở trên
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        return line.split(':')[1].strip()
        except:
            return "0000000000000000"
            
    elif get_flatform() == "Windows":
        # Lấy UUID cho Windows
        cmd = 'wmic baseboard get serialnumber'
        return subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
    
    return "Unknown_Device"


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

# Media
VIDEO_DIR = Path(r"/home/tuanlt/Videos") if PLATFORM_SYSTEM == "Linux" else Path(r"D:\Outsource\RFID\Video")
HOME_PATH = Path(r"D:\Outsource\RFID\JPG\Home.jpg")
CFG_PATH = Path(r"config.yaml")

# Mqtt
CLIENT_ID = get_device_id()

BROKER = "192.168.137.1"
PORT = 1883

TOPIC_CHECK_INFO    = "/topic/check/info"
TOPIC_INFO          = "/topic/info"
TOPIC_VIDEO         = f"/topic/video/{CLIENT_ID}"
TOPIC_VIDEO_STT     = f"/topic/video/status/{CLIENT_ID}"

USENAME = "admin"
PASSWORD = "admin"

POLL_REGISTER_SUB = 2000

