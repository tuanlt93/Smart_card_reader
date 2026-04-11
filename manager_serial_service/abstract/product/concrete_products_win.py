from .abstract_product import SerialPort, MqttClient
from typing import List, Optional, Tuple, Dict, Callable, Any
from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from utils.logger import Logger
import serial
import yaml
import sys
import queue
import json
import threading
import time
from constant import (SERIAL_PORT, BAURATE, MAX_BACKOFF, MIN_BACKOFF,
                      BROKER, PORT, TOPIC_DEVICE, TOPIC_DEVICE_STT, USENAME, 
                      PASSWORD, CLIENT_ID)        

class Singleton:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

# ──────────────────────────────────────────────────────────────
# Concrete Products - Serial
# ──────────────────────────────────────────────────────────────
class WindownsSerialPort(Singleton, SerialPort):
    def __init__(self):
        # Giả định các hằng số này đã được import từ config.py
        self.__port = SERIAL_PORT
        self.__baud = BAURATE
        self.__ser: Optional[serial.Serial] = None

        self.__max_backoff = MAX_BACKOFF
        self.__min_backoff = MIN_BACKOFF
        self.__backoff_time = self.__min_backoff

        self.__datas_pre_send = queue.Queue(maxsize=30)
        self.__datas_send = queue.Queue(maxsize=30)
        self.__running = True

        # Thread 1: Duy trì kết nối
        self.__maintain_thread = threading.Thread(target=self.__maintain_loop, daemon=True)
        self.__maintain_thread.start()

        # Thread 2: Gửi dữ liệu
        self.__send_thread = threading.Thread(target=self.__send_data_loop, daemon=True)
        self.__send_thread.start()

    def __maintain_loop(self) -> None:
        while self.__running:
            if not self.is_opened():
                if self.__open_connection():
                    self.__backoff_time = self.__min_backoff
                else:
                    time.sleep(self.__backoff_time)
                    self.__backoff_time = min(self.__backoff_time * 2, self.__max_backoff)
                    continue
            time.sleep(2)

    def __open_connection(self) -> bool:
        try:
            self.close()
            
            self.__ser = serial.Serial(
                port=self.__port,
                baudrate=self.__baud,
                timeout=0.2,        # Quan trọng cho readline()
                write_timeout=0.1,
                dsrdtr=False,
                rtscts=False
            )
            # 1. Đợi một chút cho phần cứng ổn định (0.5s là đủ)
            time.sleep(0.5) 
            
            # 2. BƯỚC QUAN TRỌNG: Xả sạch buffer cũ 
            # Đọc bỏ sạch sành sanh những gì ESP32 đã gửi trong 0.5s qua
            if self.__ser.in_waiting > 0:
                self.__ser.read(self.__ser.in_waiting)

            self.__ser.reset_input_buffer()
            self.__ser.reset_output_buffer()
            Logger().info(f"[Serial] Serial connected: {self.__port}")
            return True
        except (serial.SerialException, OSError) as e:
            self.__ser = None
            Logger().error(f"[Serial] Serial connection failed: {e}")
            return False

    def close(self) -> None:
        if self.__ser:
            self.__ser.close()
            self.__ser = None

    def receive_datas(self) -> List[Dict]:
        """Đọc và giải mã JSON từ Serial"""
        lines = []
        if not self.is_opened():
            return lines

        try:
            while self.__ser.in_waiting > 0:
                # Dùng errors='ignore' để tránh crash do nhiễu tín hiệu
                raw_line = self.__ser.readline().decode('utf-8', errors='ignore').strip()
                if not raw_line:
                    continue
                
                try:
                    data = json.loads(raw_line)
                    lines.append(data)
                except json.JSONDecodeError:
                    Logger().warning(f"[Serial] Message receice must is json: {raw_line}")
        except (serial.SerialException, OSError) as e:
            Logger().error(f"[Serial] Serial Read Error: {e}")
            self.close()
        return lines

    def add_data_send(self, data: Dict) -> None:
        """ Thêm dữ liệu vào hàng đợi gửi (nên cho phép kể cả khi chưa mở port)
            "cmd": "io",
            "data": {
                    "D1": 1,
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
        if isinstance(data, Dict):
            self.__datas_pre_send.put(data)
        else:
            Logger().warning(f"[Serial] Message send must is dict: {data}")
        
    def __send_data_loop(self) -> None:
        while self.__running:
            # 1. Lấy tất cả tin nhắn hiện có trong hàng đợi sơ cấp
            raw_batch = []

            while not self.__datas_pre_send.empty():
                try:
                    raw_batch.append(self.__datas_pre_send.get_nowait())
                    self.__datas_pre_send.task_done()
                except queue.Empty:
                    break

            # 2. Gom nhóm các lệnh io lại với nhau
            if raw_batch:
                io_buffer = {}
            
                for msg in raw_batch:
                    cmd = msg.get("cmd")
                    data = msg.get("data")

                    if cmd == "io":
                        for key, value in data.items():
                            io_buffer[key] = value

                            # Nếu buffer đạt 10 keys, đóng gói và reset buffer
                            if len(io_buffer) >= 5:
                                self.__datas_send.put({"cmd": "io", "data": io_buffer.copy()})
                                io_buffer.clear()
                    else:
                        # Gặp lệnh KHÔNG PHẢI "io" (reset, blink...):
                        # BƯỚC 1: Xả buffer "io" hiện tại ra trước để giữ đúng thứ tự thời gian
                        if io_buffer:
                            self.__datas_send.put({"cmd": "io", "data": io_buffer.copy()})
                            io_buffer.clear()

                        # BƯỚC 2: Đưa lệnh đặc biệt vào hàng đợi
                        self.__datas_send.put(msg)

                # Cuối batch, nếu vẫn còn dư key trong io_buffer thì đẩy nốt
                if io_buffer:
                    self.__datas_send.put({"cmd": "io", "data": io_buffer})

            try:
                msg = self.__datas_send.get(block=True, timeout=0.1)
                if self.is_opened():
                    try:
                        json_str = json.dumps(msg, separators=(',', ':')) + "\n"
                        self.__ser.write(json_str.encode('utf-8'))
                        self.__datas_send.task_done()
                        time.sleep(0.1)  # Thời gian nghỉ giữa các lệnh để tránh quá tải Serial
                    except (serial.SerialException, OSError) as e:
                        Logger().error(f"[Serial] Write error: {e}")
                        self.close()

            except queue.Empty:
                continue

    def is_opened(self) -> bool:
        return bool(self.__ser and self.__ser.is_open)


# ──────────────────────────────────────────────────────────────
# Concrete MQTT
# ──────────────────────────────────────────────────────────────
class WindownsMqttClient(Singleton, MqttClient):
    def __init__(self, broker: str = "192.168.137.1", port: int = 1883):
        self.__broker = broker
        self.__port = port
        self.__client_id = f"serial_{CLIENT_ID}"

        # Danh sách lưu các topic đã đăng ký để tự động sub lại khi session bị mất hoặc broker reset
        self.__subscribed_topics = {}
        
        # Initialize client with CallbackAPIVersion.VERSION2 (Required for paho-mqtt 2.0+)
        self.__client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=self.__client_id,
            clean_session=False
        )
        
        # Uncomment if authentication is required
        # self.__client.username_pw_set(USERNAME, PASSWORD)

        # State and control variables
        self.__running = True

        # Register system callbacks
        self.__client.on_connect = self.__on_connect
        self.__client.on_disconnect = self.__on_disconnect
        self.__client.on_message = self.__on_default_message
        self.__client.on_subscribe = self.__on_subscribe

        # Chỉ gọi loop_start MỘT LẦN DUY NHẤT
        # Thư viện Paho sẽ tự động handle việc reconnect ngầm
        self.__client.connect_async(self.__broker, self.__port, keepalive=10)
        self.__client.loop_start()

        # Start background maintenance thread
        self.__maintain_thread = threading.Thread(target=self.__maintain_loop, daemon=True)
        self.__maintain_thread.start()

    def __maintain_loop(self) -> None:
        while self.__running:
            if not self.is_connected():
                Logger().warning("[MQTT] System is offline. Paho is attempting to reconnect...")
            time.sleep(5)

    def __on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            # session_present là kiểu boolean (True/False)
            session_present = flags.session_present
            Logger().info(f"[MQTT] Connected. Session present: {session_present}")
            
            # Re-subscribe để đảm bảo dữ liệu luôn được nhận kể cả khi Broker bị mất dữ liệu session
            for topic, qos in self.__subscribed_topics.items():
                self.__client.subscribe(topic, qos=qos)
                if not session_present:
                    Logger().info(f"[MQTT] New session created: Subscribing to {topic}")
        else:
            Logger().error(f"[MQTT] Connection error with reason code: {reason_code}")

    def __on_disconnect(self, client, userdata, flags, reason_code, properties):
        Logger().warning(f"[MQTT] Disconnected from MQTT Broker, reason code: {reason_code}")

    def __on_default_message(self, client, userdata, msg):
        """Default handler for topics without specific callbacks"""
        try:
            payload = msg.payload.decode()
            Logger().info(f"[MQTT] Topic: {msg.topic} | Payload: {payload}")
        except Exception as e:
            Logger().error(f"[MQTT] Error decoding default message: {e}")

    def __on_subscribe(self, client, userdata, mid, reason_code_list, properties):
        Logger().info(f"[MQTT] subscription confirmed (MID: {mid})")

    def is_connected(self) -> bool:
        return self.__client.is_connected()

    def publisher(self, topic: str, payload: Dict, qos: int = 0, retain: bool = False):
        """Publish data to Broker, automatically handles JSON objects"""
        if self.is_connected():
            try:
                # Convert to JSON string if payload is dict or list
                if isinstance(payload, dict):
                    final_payload = json.dumps(payload)
                else:
                    final_payload = str(payload)

                result = self.__client.publish(topic, final_payload, qos=qos, retain=retain)
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    Logger().info(f"[MQTT] Published to '{topic}': {final_payload}")
                    return True
                else:
                    Logger().error(f"[MQTT] Publish failed with error code: {result.rc}")
            except Exception as e:
                Logger().error(f"[MQTT] Publish exception: {e}")
        else:
            Logger().warning(f"[MQTT] not connected, cannot publish to {topic}")
        return False

    def subscriber(self, topic: str, qos: int = 0, callback: Callable = None):
        """
        Subscribe to a topic with a custom callback supporting args and kwargs.
        Automatically handles message filtering via Paho's message_callback_add.
        """
        self.__subscribed_topics[topic] = qos
        if callback:
            def message_wrapper(client, userdata, msg):
                try:
                    # Pass the message and custom arguments to the user callback
                    payload_str = msg.payload.decode('utf-8', errors='ignore')
                    try:
                        processed_payload = json.loads(payload_str)
                        if isinstance(processed_payload, Dict):
                            callback(processed_payload)
                        else:
                            Logger().warning(f"[MQTT] Message send must is dict: {payload_str}")

                    except json.JSONDecodeError:
                        Logger().warning(f"[MQTT] Message send must is json: {payload_str}")


                except Exception as e:
                    Logger().error(f"[MQTT] Error in MQTT callback for topic {topic}: {e}")

            # Add specific callback for this topic
            self.__client.message_callback_add(topic, message_wrapper)
        
        # Execute subscription
        self.__client.subscribe(topic, qos = qos)
        
        if self.is_connected():
            Logger().info(f"[MQTT] Subscription request sent for: {topic}")
        else:
            Logger().warning(f"[MQTT] currently offline, subscription for {topic} will be active upon reconnection")

    def disconnect(self):
        """Gracefully stop MQTT client"""
        self.__running = False
        self.__client.loop_stop()
        self.__client.disconnect()
        Logger().info("[MQTT] Client connection stopped")