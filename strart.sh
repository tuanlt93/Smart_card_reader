#!/bin/sh
create_systemd_service() {
    service_file_content="
# /etc/systemd/system/rfid_video.service
[Unit]
Description=RFID Video Loop
After=graphical.target network-online.target sound.target
Wants=graphical.target network-online.target sound.target

[Service]
Type=simple

# --- Môi trường X11 ---
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/pi/.Xauthority   # đường dẫn của user

# --- User / quyền ---
User=pi
Group=pi
# Nếu bạn đã tạo /dev/rfid0 với MODE=0660 GROUP=dialout
SupplementaryGroups=dialout

ExecStartPre=/bin/sh -c 'for i in \$(seq 1 20); do /usr/bin/amixer -c 2 sset "PCM" 100% unmute && exit 0; sleep 1; done; exit 1'

# --- Thư mục & lệnh chạy ---
WorkingDirectory=/home/pi/RFID
ExecStart=/home/pi/RFID/venv/bin/python3 /home/pi/RFID/main.py

# --- Tự khởi động lại khi lỗi ---
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
"

    echo "$service_file_content" | sudo tee /etc/systemd/system/rfid_video.service
    
    sudo systemctl daemon-reload
    sudo systemctl enable rfid_video.service
    sudo systemctl start rfid_video.service
    echo "Systemd unit file created and service started."
}

create_systemd_service
echo "Finish setting up the environment"
