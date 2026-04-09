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
    
def get_serial() -> str:
    if platform.system() == "Linux":
        return "/dev/device0"
    elif platform.system() == "Windows":
        return "COM3"
    else:
        return "None"

class StructMsg:
    CMD = "cmd"
    DATA = "data"
    FEEDBACK = "feedback"
    INFO = "info"

# Main
PLATFORM_SYSTEM = get_flatform()

# Serial
SERIAL_PORT = get_serial()
BAURATE = 115200
MAX_BACKOFF = 5
MIN_BACKOFF = 1
POLL_SERIAL = 0.1

# Mqtt
CLIENT_ID = get_device_id()

BROKER = "192.168.137.1"
PORT = 1883

TOPIC_CHECK_INFO    = "/topic/check/info"
TOPIC_INFO          = "/topic/info"
TOPIC_DEVICE        = f"/topic/device/{CLIENT_ID}"
TOPIC_DEVICE_STT    = f"/topic/device/status/{CLIENT_ID}"

USENAME = "admin"
PASSWORD = "admin"

POLL_REGISTER_SUB = 2

