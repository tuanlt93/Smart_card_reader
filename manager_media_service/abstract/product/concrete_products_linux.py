from .abstract_product import Config, MediaEngine, MqttClient
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
from constant import (EXPORT_DISPLAY,
                      VIDEO_DIR, HOME_PATH, CFG_PATH, MediaState, StructMsg,
                      BROKER, PORT,
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
# Concrete MQTT
# ──────────────────────────────────────────────────────────────
class LinuxMqttClient(Singleton, MqttClient):
    def __init__(self, broker: str = "192.168.137.1", port: int = 1883):
        self.__broker = broker
        self.__port = port
        self.__client_id = f"media_{CLIENT_ID}"

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
                self.__screen_width = self.__root.winfo_screenwidth()
                self.__screen_height = self.__root.winfo_screenheight()

                # self.__screen_width = 1080
                # self.__screen_height = 720

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
                self._safe_shutdown()

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
    
    def _safe_shutdown(self, event=None):
        """Placeholder for shutdown logic - to be overridden by Engine"""
        pass

# ──────────────────────────────────────────────────────────────
# Concrete Products - MEDIA (VLC)
# ──────────────────────────────────────────────────────────────
class LinuxVLCMediaEngine(LinuxTkinterUI, MediaEngine):
    def __init__(self, uid_map: Dict[str, str], mqtt_client: MqttClient):
        # Chọn options theo OS
        self.__opts = [
            "--no-video-title-show",
            "--fullscreen",
            "--quiet",
            "--network-caching=2000",
            "--file-caching=2000",
            
            # Đồng bộ hóa cực đoan
            "--drop-late-frames",
            "--skip-frames",
            
            # Âm thanh
            "--aout=alsa",
            "--alsa-audio-device=default",
            
            # XUẤT HÌNH TRỰC TIẾP (DRM/KMS)
            # Bỏ qua hoàn toàn X11 để tránh crash HDMI
            "--vout=drm", 
            "--no-xlib",
            "--gain=1.0",
            
            # Giải mã phần cứng
            "--avcodec-hw=v4l2m2m",
            
            # Tối ưu tài nguyên
            "--no-osd",
            "--avcodec-skiploopfilter=4",
            "--no-stats",
            "--no-mouse-events",
        ] 
        super().__init__()

        self.__uid_map = uid_map
        self.__mqtt_client = mqtt_client
        self.__export_display = EXPORT_DISPLAY

        self.__vlc = vlc.Instance(self.__opts)
        self.__player = self.__vlc.media_player_new()

        self.__root_ui: Optional[tkinter.Tk] = self.root_ui()
        self.__canvas: Optional[tkinter.Canvas] = self.canvas_ui()
        self.__home_lbl: Optional[tkinter.Label] = self.home_lbl()

        # Setup linux close protocol
        if self.__export_display and self.__root_ui:
            self.__root_ui.bind("<Escape>", lambda e: self._safe_shutdown())
            self.__root_ui.protocol("WM_DELETE_WINDOW", self._safe_shutdown)

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
            media.add_option(":avcodec-hw=v4l2m2m")
            media.add_option(":avcodec-skiploopfilter=4")
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

    
    def _safe_shutdown(self, event = None) -> None:
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
            # Close connection
            self.__mqtt_client.disconnect()
        except Exception as e:
            Logger().error(f"[Tkinter] Error closing serial: {str(e)}")
        
        try:
            # Destroy window if it exists
            if self.__root_ui:
                self.__root_ui.destroy()
        except tkinter.TclError:
            pass  # Window already destroyed
        
        Logger().info("[App] Shutdown complete.")
        sys.exit(0)


