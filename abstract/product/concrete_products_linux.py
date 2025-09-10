from .abstract_product import Config, SerialPort, MediaEngine
from typing import List, Optional, Tuple, Dict, Callable
from pathlib import Path
from PIL import Image, ImageTk
from utils.logger import Logger
import serial
import tkinter
import vlc
import yaml
import sys
import gc

class Singleton:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


# --- Concrete Products for Linux ---

class LinuxConfig(Config):
    def __init__(self):
        self.__video_dir    = Path(r"/home/pi/Videos")
        self.__home_img     = Path(r"/home/pi/RFID/JPG/Home.jpg")
        self.__cfg          = Path(r"/home/pi/RFID/config.yaml")
        self.__serial       = "/dev/rfid0"
        self.__baudrate     = 115200

    def serial_port_name(self) -> str: return self.__serial

    def baudrate(self) -> int: return self.__baudrate

    def home_img(self) -> Path: return self.__home_img

    def load_config(self) -> Dict[str, str]:
        try:
            with self.__cfg.open(encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            uid_map = {}
            for uid, fname in cfg.get("uid_map", {}).items():
                path = (self.__video_dir / fname).resolve()
                if not path.exists():
                    Logger().error(f"Video file not found: {path}")
                    continue
                uid_map[uid] = str(path)
            if not uid_map:
                Logger().error("No valid videos found in configuration")
            return uid_map
        except Exception as e:
            Logger().error(f"Configuration error: {e}")
            raise

    
        

# ──────────────────────────────────────────────────────────────
# Concrete Products - Serial
# ──────────────────────────────────────────────────────────────
class LinuxSerialPort(Singleton ,SerialPort):
    def __init__(self, port_name: str = "/dev/rfid0", baudrate: int = 115200):
        self.__port = port_name
        self.__baud = baudrate
        self.__ser: Optional[serial.Serial] = None

        self.__max_backoff = 16  # Giới hạn thời gian backoff tối đa là 30 giây
        self.__min_backoff = 1  # Thời gian chờ tối thiểu là 2 giây
        self.__backoff_time = self.__min_backoff
        self.__error_count = 0

        self.open()

        
    def open(self) -> None:
        if self.__ser:
            self.__ser = None
        try:
            self.__ser = serial.Serial(
                self.__port,
                self.__baud,
                timeout=0.1,
                write_timeout=0.1
            )
            self.__backoff_time = self.__min_backoff
            Logger().info(f"Serial connected: {self.__port}")
        except (serial.SerialException, OSError) as e:
            self.__ser = None
            Logger().error(f"Serial connection failed: {str(e)}, reconnect after {self.__backoff_time}s")
            

    def close(self) -> None:
        if self.is_opened():
            self.__ser.close()
            self.__ser = None
    
    def receive_datas(self) -> list[str]:
        lines = []
        try:
            while self.__ser.in_waiting > 0:
                s = self.__ser.readline().decode("utf-8", "ignore").strip()
                if s:
                    lines.append(s)
        except (serial.SerialException, OSError) as e:
            self.close()
            Logger().error(f"Serial error: {e}")
        return lines
    
    def is_opened(self) -> bool:
        return bool(self.__ser and self.__ser.is_open)
            
    def get_time_polling(self):
        self.__error_count += 1
        # Tăng thời gian backoff theo cấp số nhân nhưng không vượt quá giới hạn
        self.__backoff_time = min(self.__backoff_time * 2, self.__max_backoff)
        return self.__backoff_time



# ──────────────────────────────────────────────────────────────
# Concrete Products - UI
# ──────────────────────────────────────────────────────────────
class LinuxTkinterUI(Singleton):
    def __init__(self, home_img_path: Path):
        self.__home_img : Path          = home_img_path
        self.__root = tkinter.Tk()
        self.__root.update_idletasks()

        # # Get screen dimensions
        self.__screen_width = self.__root.winfo_screenwidth()
        self.__screen_height = self.__root.winfo_screenheight()

        self.__root.geometry(f"{self.__screen_width}x{self.__screen_height}+0+0")
        self.__root.attributes("-fullscreen", False)
        self.__root.config(cursor="none")
        
        # Preload home image
        try:
            img = Image.open(self.__home_img)
            resample = Image.NEAREST
            img = img.resize((self.__screen_width, self.__screen_height), resample)
            self.home_photo = ImageTk.PhotoImage(img)
        except Exception as e:
            Logger().error(f"Error loading home image: {str(e)}")
            # Create blank image as fallback
            self.home_photo = ImageTk.PhotoImage(Image.new('RGB', (self.__screen_width, self.__screen_height), 'black'))
        
        # Create UI elements
        self.__canvas = tkinter.Canvas(self.__root, bg="black", highlightthickness=0)
        self.__home_lbl = tkinter.Label(self.__root, image=self.home_photo)
        self.__home_lbl.place(x=0, y=0, relwidth=1, relheight=1)

    def root_ui(self) -> tkinter.Tk:
        return self.__root
    
    def canvas_ui(self) -> tkinter.Canvas:
        return self.__canvas
    
    def home_lbl(self) -> tkinter.Label:
        return self.__home_lbl

    def mainloop(self) -> None:
        return self.__root.mainloop()

    def run_loop_after_time(self, poll_time_ms: int, func: Callable) -> str:
        return self.__root.after(poll_time_ms, func)
    
    def cancel_run_loop_after_time(self, job: str) -> None:
        return self.__root.after_cancel(job)


# ──────────────────────────────────────────────────────────────
# Concrete Products - MEDIA (VLC)
# ──────────────────────────────────────────────────────────────
class LinuxVLCMediaEngine(LinuxTkinterUI, MediaEngine):
    def __init__(self, home_img_path: Path, uid_map: Dict[str, str], serial_port: SerialPort):
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
            "--gain=1.0"
            "--no-xlib",                 # tránh phụ thuộc X11
            "--vout=drm",                # xuất trực tiếp KMS
            "--avcodec-hw=v4l2m2m",      # giải mã HW
        ] 

        super().__init__(home_img_path)

        self.__serial_port = serial_port

        self.__vlc = vlc.Instance(self.__opts)
        self.__player = self.__vlc.media_player_new()

        self.__root_ui: Optional[tkinter.Tk] = self.root_ui()
        self.__canvas: Optional[tkinter.Canvas] = self.canvas_ui()
        self.__home_lbl: Optional[tkinter.Label] = self.home_lbl()

        # Setup linux close protocol
        self.__root_ui.bind("<Escape>", lambda e: self.__safe_shutdown())
        self.__root_ui.protocol("WM_DELETE_WINDOW", self.__safe_shutdown)

        self.__current_uid = ""
        self.__media_cache = {}
        self.__uid_map = uid_map

        # Set canvas window ID
        self.__root_ui.update_idletasks()
        self.__player.set_xwindow(self.__canvas.winfo_id())
        
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
        if self.__current_uid:
            self.__root_ui.after(0, self.__restart_video)

    def __restart_video(self):
        """Restart the current video"""
        if self.__current_uid and self.__player:
            try:
                # Use cached media
                media = self.__get_media(self.__current_uid)
                self.__player.set_media(media)
                self.__player.play()
                Logger().debug(f"Restarted video for UID: {self.__current_uid}")
            except Exception as e:
                Logger().error(f"Error restarting video: {str(e)}")

    def show_home(self) -> None:
        """Show home screen"""
        if self.__current_uid:
            try:
                self.__player.stop()
                # Release media player resources
                self.__player.set_media(None)
                gc.collect()
            except Exception as e:
                Logger().error(f"Error stopping player: {str(e)}")
            self.__current_uid = ""
            
        self.__canvas.place_forget()
        self.__home_lbl.place(x=0, y=0, relwidth=1, relheight=1)

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
                self.__home_lbl.place_forget()
                self.__canvas.place(x=0, y=0, relwidth=1, relheight=1)
                
                Logger().info(f"Playing video for UID: {uid}")
            
        except Exception as e:
            Logger().error(f"Video play error: {str(e)}")
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
            Logger().warning(f"Watchdog: player state={state}, restarting")
            try:
                self.__player.stop()
                self.__player.release()
            except Exception:
                pass
            # tạo MediaPlayer mới rồi gắn vào cửa sổ
            self.__player = self.__vlc.media_player_new()
            self.__attach_player_window()
            self.__restart_video()        # phát lại video hiện tại / về màn hình home
        # gọi lại sau 10 s
        self.__root_ui.after(10_000, self.__watch_player)

    
    def __safe_shutdown(self, event = None) -> None:
        """Safe shutdown procedure"""
        Logger().info("Initiating safe shutdown")
        
        try:
            # Release VLC resources
            if self.__player:
                self.__player.stop()
                self.__player.release()
        except Exception as e:
            Logger().error(f"Error releasing VLC: {str(e)}")
        
        try:
            # Close serial connection
            self.__serial_port.close()
        except Exception as e:
            Logger().error(f"Error closing serial: {str(e)}")
        
        try:
            # Destroy window if it exists
            if self.__root_ui:
                self.__root_ui.destroy()
        except tkinter.TclError:
            pass  # Window already destroyed
        
        sys.exit(0)


