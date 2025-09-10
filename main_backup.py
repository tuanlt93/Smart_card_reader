
#!/usr/bin/env python3
"""
RFID Video Loop - Highly Optimized for Raspberry Pi 4B
---------------------------------------------------
• Extreme performance optimizations
• Reduced CPU usage
• Better resource management
"""
from __future__ import annotations
import platform
import serial
import tkinter as tk
from pathlib import Path
import yaml
from PIL import Image, ImageTk
import vlc
import logging
import sys
import os
import gc
import time

# ─── Configuration ────────────────────────────────────────────
# Optimize for Raspberry Pi
IS_RASPBERRY = platform.system() == "Linux"

if IS_RASPBERRY:
    VIDEO_DIR   = Path(r"/home/raspberrypi/Videos")
    HOME_IMG    = Path(r"/home/raspberrypi/RFID/Home/Home.jpg")
    CONFIG_PATH = Path(r"/home/raspberrypi/RFID/config.yaml")
    SERIAL_PORT = "/dev/rfid0"
else:
    VIDEO_DIR   = Path(r"D:\Outsource\RFID\Video")
    HOME_IMG    = Path(r"D:\Outsource\RFID\JPG\Home.jpg")
    CONFIG_PATH = Path(r"D:\Outsource\RFID\config.yaml")
    SERIAL_PORT = "COM20"

BAUDRATE = 9600
POLL_MS = 200          # Increased polling interval to reduce CPU
RECON_MS = 2000        # Longer reconnect interval

# Setup logging
log_file = "rfid_player.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        # logging.StreamHandler()
    ]
)

# ─── Main Class ───────────────────────────────────────────────
class RFIDVideoPlayer:
    def __init__(self) -> None:
        # Initialize state
        self.current_uid = None
        self.media_cache = {}
        self.recon_job = None
        self.ser = None
        self.home_photo = None
        self.last_command = None
        self.last_command_time = 0
        
        try:
            # Load configuration
            self.load_config()
            
            # Setup UI
            self.init_ui()
            
            # Setup VLC
            self.init_vlc()
            self._watch_player()
            
            # Preload media AFTER VLC is initialized
            self.preload_media()
            
            # Initial serial connection
            self.connect_serial()
            
            # Start main loop
            self.root.after(POLL_MS, self.poll_serial)
            self.root.mainloop()
        except Exception as e:
            logging.critical(f"Initialization failed: {str(e)}", exc_info=True)
            self.safe_shutdown()

    def load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            with CONFIG_PATH.open(encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            
            self.uid_map = {}
            for uid, fname in cfg["uid_map"].items():
                path = (VIDEO_DIR / fname).resolve()
                if not path.exists():
                    logging.error(f"Video file not found: {path}")
                    continue
                self.uid_map[uid] = str(path)
                
            if not self.uid_map:
                raise RuntimeError("No valid videos found in configuration")
                
        except Exception as e:
            logging.critical(f"Configuration error: {str(e)}")
            raise

    def preload_media(self) -> None:
        """Preload media for faster access"""
        # Only preload on non-Pi systems
        if not IS_RASPBERRY:
            for uid in self.uid_map:
                self.get_media(uid)
            logging.info("Preloaded media for all UIDs")

    def init_ui(self) -> None:
        """Initialize the user interface"""
        self.root = tk.Tk()
        self.root.update_idletasks()

        # # Get screen dimensions
        # self.screen_width = self.root.winfo_screenwidth()
        # self.screen_height = self.root.winfo_screenheight()

        self.screen_width = 1080
        self.screen_height = 720

        self.root.geometry(f"{self.screen_width}x{self.screen_height}+0+0")


        self.root.attributes("-fullscreen", False)
        self.root.config(cursor="none")
        self.root.bind("<Escape>", lambda e: self.safe_shutdown())
        
        # Setup window close protocol
        self.root.protocol("WM_DELETE_WINDOW", self.safe_shutdown)
        
        
        
        # Preload home image
        try:
            img = Image.open(HOME_IMG)
            # Use faster resampling on Pi
            resample = Image.NEAREST if IS_RASPBERRY else Image.LANCZOS
            img = img.resize((self.screen_width, self.screen_height), resample)
            self.home_photo = ImageTk.PhotoImage(img)
        except Exception as e:
            logging.error(f"Error loading home image: {str(e)}")
            # Create blank image as fallback
            self.home_photo = ImageTk.PhotoImage(Image.new('RGB', (self.screen_width, self.screen_height), 'black'))
        
        # Create UI elements
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.home_lbl = tk.Label(self.root, image=self.home_photo)
        self.home_lbl.place(x=0, y=0, relwidth=1, relheight=1)

    def init_vlc(self) -> None:
        """Initialize VLC player with optimized settings"""
        # VLC options
        opts = []
        # Raspberry Pi specific optimizations
        if IS_RASPBERRY:
            opts += [
            "--no-video-title-show",
            "--fullscreen",
            "--network-caching=500",
            "--file-caching=500",
            "--drop-late-frames",
            "--skip-frames",
            "--quiet",
            "--aout=alsa",
            "--alsa-audio-device=hw:2,0",
            "--no-xlib",                 # tránh phụ thuộc X11
            "--vout=drm",                # xuất trực tiếp KMS
            "--avcodec-hw=v4l2m2m",      # giải mã HW
        ] 
        else:
            opts += [
            "--no-xlib",  # Disable Xlib for better performance
            "--no-video-title-show",
            "--network-caching=500",
            "--quiet",
            "--drop-late-frames",
            "--skip-frames",
            "--no-snapshot-preview", 
            "--avcodec-skiploopfilter=all",
            "--avcodec-skip-frame=nonref",
            "--avcodec-skip-idct=nonref",
            "--avcodec-fast",
            "--avcodec-threads=0",  # Use all cores
            "--avcodec-hw=none",
            "--vout=direct3d9"
        ]
            
        self.vlc = vlc.Instance(opts)
        self.player = self.vlc.media_player_new()
        
        # Set canvas window ID
        self.root.update_idletasks()  # Ensure window is ready
        if IS_RASPBERRY:
            self.player.set_xwindow(self.canvas.winfo_id())
        else:
            self.player.set_hwnd(self.canvas.winfo_id())
        
        # Setup end of video event handling
        self.event_manager = self.player.event_manager()
        self.event_manager.event_attach(
            vlc.EventType.MediaPlayerEndReached,
            self._on_video_end
        )

    def get_media(self, uid: str) -> vlc.Media:
        """Get media from cache or create new with optimizations"""
        media = self.media_cache.get(uid)
        if not media:
            media = self.vlc.media_new(self.uid_map[uid])
            # Add media options for performance
            media.add_option(":avcodec-hw=any")
            media.add_option(":no-avcodec-dr")
            media.add_option(":avcodec-skiploopfilter=all")
            self.media_cache[uid] = media
        return media

    def _on_video_end(self, event):
        """Handle end of video event"""
        # Schedule restart in main thread
        if self.current_uid:
            self.root.after(0, self._restart_video)

    def _restart_video(self):
        """Restart the current video"""
        if self.current_uid and self.player:
            try:
                # Use cached media
                media = self.get_media(self.current_uid)
                self.player.set_media(media)
                self.player.play()
                logging.debug(f"Restarted video for UID: {self.current_uid}")
            except Exception as e:
                logging.error(f"Error restarting video: {str(e)}")

    def connect_serial(self) -> None:
        """Attempt to connect to serial device"""
        if self.recon_job:
            self.root.after_cancel(self.recon_job)
            self.recon_job = None
            
        try:
            self.ser = serial.Serial(
                SERIAL_PORT,
                BAUDRATE,
                timeout=0.1,
                write_timeout=0.1
            )
            logging.info(f"Serial connected: {SERIAL_PORT}")
        except (serial.SerialException, OSError) as e:
            logging.warning(f"Serial connection failed: {str(e)}")
            self.ser = None
            self.recon_job = self.root.after(RECON_MS, self.connect_serial)

    def poll_serial(self) -> None:
        """Poll serial device for data"""
        try:
            if self.ser and self.ser.is_open:
                # Read all available lines to prevent buffer buildup
                lines = []
                while self.ser.in_waiting > 0:
                    line = self.ser.readline().decode("utf-8", "ignore").strip()
                    if line:
                        lines.append(line)
                
                # Process last line only (most recent state)
                if lines:
                    self.process_rfid_command(lines[-1])

                
        except (serial.SerialException, OSError) as e:
            logging.error(f"Serial error: {str(e)}")
            self.ser = None
            self.connect_serial()
        finally:
            self.root.after(POLL_MS, self.poll_serial)

    def process_rfid_command(self, command: str) -> None:
        """Process RFID commands with deduplication"""
        current_time = time.monotonic()
        
        # Skip duplicate commands within 200ms
        if command == self.last_command and (current_time - self.last_command_time) < 0.2:
            return
            
        self.last_command = command
        self.last_command_time = current_time
        
        if command == "removed":
            self.show_home()
        elif command in self.uid_map:
            if command != self.current_uid:
                self.play_video(command)

    def show_home(self) -> None:
        """Show home screen"""
        if self.current_uid:
            try:
                self.player.stop()
                # Release media player resources
                self.player.set_media(None)
                # Force garbage collection on Pi
                if IS_RASPBERRY:
                    gc.collect()
            except Exception as e:
                logging.error(f"Error stopping player: {str(e)}")
            self.current_uid = None
            
        self.canvas.place_forget()
        self.home_lbl.place(x=0, y=0, relwidth=1, relheight=1)

    def play_video(self, uid: str) -> None:
        """Play video for specified UID"""
        try:
            # Get media
            media = self.get_media(uid)
            
            # Set media and play
            self.player.set_media(media)
            self.player.play()
            self.current_uid = uid
            
            # Show video canvas
            self.home_lbl.place_forget()
            self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
            
            logging.info(f"Playing video for UID: {uid}")
            
        except Exception as e:
            logging.error(f"Video play error: {str(e)}")
            self.show_home()

    def safe_shutdown(self, event=None) -> None:
        """Safe shutdown procedure"""
        logging.info("Initiating safe shutdown")
        
        try:
            # Release VLC resources
            if hasattr(self, 'player') and self.player:
                self.player.stop()
                self.player.release()
        except Exception as e:
            logging.error(f"Error releasing VLC: {str(e)}")
        
        try:
            # Close serial connection
            if hasattr(self, 'ser') and self.ser and self.ser.is_open:
                self.ser.close()
        except Exception as e:
            logging.error(f"Error closing serial: {str(e)}")
        
        try:
            # Destroy window if it exists
            if hasattr(self, 'root') and self.root:
                self.root.destroy()
        except tk.TclError:
            pass  # Window already destroyed
        
        sys.exit(0)
        
        
    def _attach_player_window(self):
        """Liên kết MediaPlayer mới với cửa sổ Tk."""
        self.root.update_idletasks()
        if IS_RASPBERRY:
            self.player.set_xwindow(self.canvas.winfo_id())
        else:
            self.player.set_hwnd(self.canvas.winfo_id())

    def _watch_player(self):
        """Kiểm tra định kỳ trạng thái VLC; khởi tạo lại nếu lỗi."""
        state = self.player.get_state()
        if state in (vlc.State.Error, vlc.State.Stopped):
            logging.warning(f"Watchdog: player state={state}, restarting")
            try:
                self.player.stop()
                self.player.release()
            except Exception:
                pass
            # tạo MediaPlayer mới rồi gắn vào cửa sổ
            self.player = self.vlc.media_player_new()
            self._attach_player_window()
            self._restart_video()        # phát lại video hiện tại / về màn hình home
        # gọi lại sau 10 s
        self.root.after(10_000, self._watch_player)


# ─── Main Entry Point ─────────────────────────────────────────
if __name__ == "__main__":
    try:
        player = RFIDVideoPlayer()
    except Exception as e:
        logging.critical(f"Fatal error during initialization: {str(e)}", exc_info=True)
        sys.exit(1)