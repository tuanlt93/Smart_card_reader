from .abstract_product import Config, SerialPort, MediaEngine, MqttClient
from typing import List, Optional, Tuple, Dict, Callable, Any
from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from PIL import Image, ImageTk
from utils.logger import Logger
import serial
import tkinter
import vlc
import yaml
import sys
import queue
import json
import threading
import time
import gc
from constant import (SERIAL_PORT, BAURATE, MAX_BACKOFF, MIN_BACKOFF, EXPORT_DISPLAY,
                      VIDEO_DIR, HOME_PATH, CFG_PATH, MediaState, StructMsg,
                      BROKER, PORT, TOPIC_DEVICE, TOPIC_DEVICE_STT,
                      TOPIC_VIDEO, TOPIC_VIDEO_STT, USENAME, 
                      PASSWORD, CLIENT_ID)    

class Singleton:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

# --- Concrete Products for Linux ---
class LinuxConfig(Config):
    def __init__(self):
        self.__video_dir = VIDEO_DIR
        self.__cfg = CFG_PATH

    def load_config(self) -> Dict[str, str]:
        try:
            with self.__cfg.open(encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            uid_map = {}
            for uid, fname in cfg.get("uid_map", {}).items():
                path = (self.__video_dir / fname).resolve()
                if not path.exists():
                    Logger().error(f"[CFG] Video file not found: {path}")
                    continue
                uid_map[uid] = str(path)
            if not uid_map:
                Logger().error("[CFG] No valid videos found in configuration")
            return uid_map
        except Exception as e:
            Logger().error(f"[CFG] Configuration error: {e}")
            raise


# ──────────────────────────────────────────────────────────────
# Concrete Products - Serial
# ──────────────────────────────────────────────────────────────
class LinuxSerialPort(Singleton ,SerialPort):
    def __init__(self):
        # Giả định các hằng số này đã được import từ config.py
        self.__port = SERIAL_PORT
        self.__baud = BAURATE
        self.__ser: Optional[serial.Serial] = None

        self.__max_backoff = MAX_BACKOFF
        self.__min_backoff = MIN_BACKOFF
        self.__backoff_time = self.__min_backoff

        self.__datas_send = queue.Queue()
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
                self.__port,
                self.__baud,
                timeout=0.1,        # Quan trọng cho readline()
                write_timeout=0.1,
                dsrdtr=False,
                rtscts=False
            )
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
        """Thêm dữ liệu vào hàng đợi gửi (nên cho phép kể cả khi chưa mở port)"""
        if isinstance(data, Dict):
            self.__datas_send.put(data)
        else:
            Logger().warning(f"[Serial] Message send must is dict: {data}")
        
    def __send_data_loop(self) -> None:
        while self.__running:
            try:
                msg = self.__datas_send.get(block=True, timeout=0.1)
                if self.is_opened():
                    try:
                        json_str = json.dumps(msg, separators=(',', ':')) + "\n"
                        self.__ser.write(json_str.encode('utf-8'))
                        self.__datas_send.task_done()
                        time.sleep(0.05) 
                    except (serial.SerialException, OSError) as e:
                        Logger().error(f"[Serial] Write error: {e}")
                        self.__datas_send.put(msg)
                        self.close()

            except queue.Empty:
                continue

    def is_opened(self) -> bool:
        return bool(self.__ser and self.__ser.is_open)


# ──────────────────────────────────────────────────────────────
# Concrete MQTT
# ──────────────────────────────────────────────────────────────
class LinuxMqttClient(Singleton, MqttClient):
    def __init__(self, broker: str = "0.0.0.0", port: int = 1883):
        self.__broker = broker
        self.__port = port
        self.__client_id = CLIENT_ID
        
        # Initialize client with CallbackAPIVersion.VERSION2 (Required for paho-mqtt 2.0+)
        self.__client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=self.__client_id
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

        # Start background maintenance thread
        self.__maintain_thread = threading.Thread(target=self.__maintain_loop, daemon=True)
        self.__maintain_thread.start()

    def __maintain_loop(self) -> None:
        """Background loop for automatic reconnection and loop management"""
        while self.__running:
            if not self.is_connected():
                try:
                    Logger().info(f"[MQTT] Connecting to MQTT Broker: {self.__broker}:{self.__port}...")
                    # Connect and start the network loop
                    self.__client.connect(self.__broker, self.__port, keepalive=60)
                    self.__client.loop_start()
                except Exception as e:
                    Logger().error(f"[MQTT] Connection failed: {e}. Retrying in 2s...")
                    continue
            
            time.sleep(2)

    def __on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            Logger().info("[MQTT] Broker connected successfully")
        else:
            Logger().error(f"[MQTT] connection error, reason code: {reason_code}")

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

    def publisher(self, topic: str, payload: Dict, retain: bool = False):
        """Publish data to Broker, automatically handles JSON objects"""
        if self.is_connected():
            try:
                # Convert to JSON string if payload is dict or list
                if isinstance(payload, dict):
                    final_payload = json.dumps(payload)
                else:
                    final_payload = str(payload)

                result = self.__client.publish(topic, final_payload, qos=0, retain=retain)
                
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

    def subscriber(self, topic: str, callback: Callable):
        """
        Subscribe to a topic with a custom callback supporting args and kwargs.
        Automatically handles message filtering via Paho's message_callback_add.
        """
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
        self.__client.subscribe(topic, qos = 0)
        
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


# ──────────────────────────────────────────────────────────────
# Concrete Products - UI
# ──────────────────────────────────────────────────────────────
class LinuxTkinterUI(Singleton):
    def __init__(self):
        self.__export_display = EXPORT_DISPLAY
        self.__root = None
        self.__canvas = None
        self.__home_lbl = None
        self.__screen_width = 1080
        self.__screen_height = 720
        self.__running = True

        if self.__export_display:
            try:
                self.__root = tkinter.Tk()
                self.__root.update_idletasks()

                # # Get screen dimensions
                # self.__screen_width = self.__root.winfo_screenwidth()
                # self.__screen_height = self.__root.winfo_screenheight()

                self.__screen_width = 1080
                self.__screen_height = 720

                self.__root.geometry(f"{self.__screen_width}x{self.__screen_height}+0+0")
                self.__root.attributes("-fullscreen", False)
                self.__root.config(cursor="none", bg="black")
                
                # Create UI elements
                self.__canvas = tkinter.Canvas(self.__root, bg="black", highlightthickness=0)
                self.__home_lbl = tkinter.Label(self.__root, bg="black")
                self.__home_lbl.place(x=0, y=0, relwidth=1, relheight=1)
            except tkinter.TclError as e:
                Logger().error(f"[UI] Failed to init Tkinter (No Display): {e}")
                self.__export_display = False

    def root_ui(self) -> tkinter.Tk:
        return self.__root
    
    def canvas_ui(self) -> tkinter.Canvas:
        return self.__canvas
    
    def home_lbl(self) -> tkinter.Label:
        return self.__home_lbl

    def mainloop(self) -> None:
        if self.__export_display and self.__root:
            return self.__root.mainloop()
        else:
            # Headless mode: Chạy vòng lặp vô tận để giữ app hoạt động
            Logger().info("[UI] Running in Headless Mode (No GUI)")
            try:
                while self.__running:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.__running = False

    def run_loop_after_time(self, poll_time_ms: int, func: Callable) -> str:
        if self.__export_display and self.__root:
            return self.__root.after(poll_time_ms, func)
        else:
            # Giả lập 'after' bằng Thread nếu ở chế độ Headless
            def delayed_exec():
                time.sleep(poll_time_ms / 1000.0)
                if self.__running:
                    func()
            
            thread = threading.Thread(target=delayed_exec, daemon=True)
            thread.start()
            return str(thread.ident)
    
    def cancel_run_loop_after_time(self, job: str) -> None:
        if self.__export_display and self.__root and job:
            try:
                self.__root.after_cancel(job)
            except ValueError:
                pass


# ──────────────────────────────────────────────────────────────
# Concrete Products - MEDIA (VLC)
# ──────────────────────────────────────────────────────────────
class LinuxVLCMediaEngine(LinuxTkinterUI, MediaEngine):
    def __init__(self, uid_map: Dict[str, str], serial_port: SerialPort, mqtt_client: MqttClient):
        # Chọn options theo OS
        self.__opts = [
            "--no-video-title-show",
            "--fullscreen",
            "--network-caching=500",
            "--file-caching=500",
            "--drop-late-frames",
            "--skip-frames",
            "--quiet",
            "--aout=alsa",
            "--alsa-audio-device=hw:2,0",
            "--audio-replay-gain-mode=none",
            "--gain=1.0",
            "--no-xlib",                 # tránh phụ thuộc X11
            "--vout=drm",                # xuất trực tiếp KMS
            "--avcodec-hw=v4l2m2m",      # giải mã HW
        ] 
        super().__init__()

        self.__uid_map = uid_map
        self.__serial_port = serial_port
        self.__mqtt_client = mqtt_client
        self.__export_display = EXPORT_DISPLAY

        self.__vlc = vlc.Instance(self.__opts)
        self.__player = self.__vlc.media_player_new()

        self.__root_ui: Optional[tkinter.Tk] = self.root_ui()
        self.__canvas: Optional[tkinter.Canvas] = self.canvas_ui()
        self.__home_lbl: Optional[tkinter.Label] = self.home_lbl()

        # Setup linux close protocol
        if self.__export_display and self.__root_ui:
            self.__root_ui.bind("<Escape>", lambda e: self.__safe_shutdown())
            self.__root_ui.protocol("WM_DELETE_WINDOW", self.__safe_shutdown)

            # Set canvas window ID
            self.__root_ui.update_idletasks()
            self.__player.set_xwindow(self.__canvas.winfo_id())

        self.__current_uid = ""
        self.__media_cache = {}
        
        # Setup end of video event handling
        self.__event_manager = self.__player.event_manager()
        self.__event_manager.event_attach(
            vlc.EventType.MediaPlayerEndReached,
            self.__on_video_end
        )

        #Kiểm tra 10s một lần xem chương trình có dừng hay không
        self.__watch_player()

    def __on_video_end(self, event):
        """Handle end of video event"""
        # Schedule restart in main thread
        if self.__export_display and self.__root_ui:
            self.__root_ui.after(0, self.show_home)
        else:
            self.__current_uid = ""

    def __restart_video(self):
        """Restart the current video"""
        if self.__current_uid and self.__player:
            try:
                # Use cached media
                media = self.__get_media(self.__current_uid)
                self.__player.set_media(media)
                self.__player.play()
                Logger().debug(f"[Tkinter] Restarted video for UID: {self.__current_uid}")
            except Exception as e:
                Logger().error(f"[Tkinter] Error restarting video: {str(e)}")

    def show_home(self) -> None:
        """Show home screen"""
        if self.__current_uid:
            try:
                self.__player.stop()
                # Release media player resources
                self.__player.set_media(None)
                gc.collect()
            except Exception as e:
                Logger().error(f"[Tkinter] Error stopping player: {str(e)}")
            self.__current_uid = ""
        
        if self.__export_display and self.__canvas and self.__home_lbl:
            self.__canvas.place_forget()
            self.__home_lbl.place(x=0, y=0, relwidth=1, relheight=1)

        msg: Dict = {
                StructMsg.CMD: StructMsg.FEEDBACK,
                StructMsg.DATA: MediaState.STOPED
            }
        self.__mqtt_client.publisher(TOPIC_VIDEO_STT, msg)

    def play_video(self, uid: str) -> None:
        """Play video for specified UID"""
        try:
            if uid != self.__current_uid:
                # Get media
                media = self.__get_media(uid)
                
                # Set media and play
                self.__player.set_media(media)
                self.__player.play()
                self.__current_uid = uid
                
                # Show video canvas
                if self.__export_display and self.__home_lbl and self.__canvas:
                    self.__home_lbl.place_forget()
                    self.__canvas.place(x=0, y=0, relwidth=1, relheight=1)
                
                Logger().info(f"[Tkinter] Playing video for UID: {uid}")
                msg: Dict = {
                    StructMsg.CMD: StructMsg.FEEDBACK,
                    StructMsg.DATA: MediaState.PLAYING
                }
                self.__mqtt_client.publisher(TOPIC_VIDEO_STT, msg)
            
        except Exception as e:
            Logger().error(f"[Tkinter] Video play error: {str(e)}")
            self.show_home()

    def __get_media(self, uid: str) -> vlc.Media:
        """Get media from cache or create new with optimizations"""
        media = self.__media_cache.get(uid)
        if not media:
            media = self.__vlc.media_new(self.__uid_map[uid])
            # Add media options for performance
            media.add_option(":avcodec-hw=any")
            media.add_option(":no-avcodec-dr")
            media.add_option(":avcodec-skiploopfilter=all")
            self.__media_cache[uid] = media
        return media
    
    def __attach_player_window(self):
        """Liên kết MediaPlayer mới với cửa sổ Tk."""
        self.__root_ui.update_idletasks()
        self.__player.set_xwindow(self.__canvas.winfo_id())

    def __watch_player(self):
        """Kiểm tra định kỳ trạng thái VLC; khởi tạo lại nếu lỗi."""
        state = self.__player.get_state()
        if state in (vlc.State.Error, vlc.State.Stopped):
            Logger().warning(f"[Tkinter] Watchdog: player state={state}, restarting")
            try:
                self.__player.stop()
                self.__player.release()
            except Exception:
                pass
            # tạo MediaPlayer mới rồi gắn vào cửa sổ
            self.__player = self.__vlc.media_player_new()

            if self.__export_display and self.__root_ui:
                self.__attach_player_window()
                self.__restart_video()        # phát lại video hiện tại / về màn hình home

        # gọi lại sau 5s
        self.run_loop_after_time(5000, self.__watch_player)

    
    def __safe_shutdown(self, event = None) -> None:
        """Safe shutdown procedure"""
        Logger().info("[Tkinter] Initiating safe shutdown")
        
        try:
            # Release VLC resources
            if self.__player:
                self.__player.stop()
                self.__player.release()
        except Exception as e:
            Logger().error(f"[Tkinter] Error releasing VLC: {str(e)}")
        
        try:
            # Close serial connection
            self.__serial_port.close()
        except Exception as e:
            Logger().error(f"[Tkinter] Error closing serial: {str(e)}")
        
        try:
            # Destroy window if it exists
            if self.__root_ui:
                self.__root_ui.destroy()
        except tkinter.TclError:
            pass  # Window already destroyed
        
        sys.exit(0)


