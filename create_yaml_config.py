# build_config.py
from pathlib import Path
import re
import yaml

# === Cấu hình ===
VIDEO_DIR = Path(r"D:\Outsource\Bo_doc_the_thong_minh\videokfix_19_6")
HOME_PATH = "D:/Outsource/RFID/JPG/Home.jpg"   # giống ví dụ bạn đưa
OUTPUT_YAML = VIDEO_DIR / "config.yaml"        # lưu ngay trong thư mục video
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".mpg", ".mpeg", ".webm"}

HEX8 = re.compile(r"^[0-9A-Fa-f]{8}$")

def main():
    if not VIDEO_DIR.exists():
        raise SystemExit(f"Thư mục không tồn tại: {VIDEO_DIR}")

    files = sorted(
        [p.name for p in VIDEO_DIR.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
    )

    if not files:
        raise SystemExit(f"Không tìm thấy file video trong: {VIDEO_DIR}")

    uid_map = {}
    pad = len(str(len(files)))

    idx = 0
    for fname in files:
        idx += 1
        stem = Path(fname).stem
        # Nếu tên file bắt đầu bằng 8 ký tự hex → coi là UID
        first_token = stem.split("_", 1)[0]
        if HEX8.match(first_token):
            key = first_token.upper()
        else:
            key = f"PUT_UID_HERE_{idx:0{pad}d}"  # placeholder để bạn điền UID thật

        uid_map[key] = fname  # chỉ lưu tên file như ví dụ của bạn

    data = {
        "home": HOME_PATH,
        "uid_map": uid_map,
    }

    # Ghi YAML (giữ thứ tự, unicode)
    with OUTPUT_YAML.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

    print(f"Đã tạo '{OUTPUT_YAML}' với {len(files)} mục.")

if __name__ == "__main__":
    main()
