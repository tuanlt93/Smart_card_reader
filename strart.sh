#!/bin/sh
create_systemd_service() {
    service_file_content="
# /etc/systemd/system/gateway.service
[Unit]
Description=RFID Video Loop
After=graphical.target network-online.target sound.target
Wants=graphical.target network-online.target sound.target

[Service]
Type=simple

# --- Môi trường X11 ---
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/tuanlt/.Xauthority   # đường dẫn của user

# --- User / quyền ---
User=tuanlt
Group=tuanlt
# Nếu bạn đã tạo /dev/device0 với MODE=0660 GROUP=dialout
SupplementaryGroups=dialout

# Sử dụng cho pi2 pi3
ExecStartPre=/bin/sh -c 'for i in \$(seq 1 5); do /usr/bin/amixer -c 0 sset \"PCM\" 100% unmute && exit 0; sleep 1; done; exit 0'

# --- Thư mục & lệnh chạy ---
WorkingDirectory=/home/tuanlt/Smart_card_reader
ExecStart=/home/tuanlt/Smart_card_reader/venv/bin/python3 /home/tuanlt/Smart_card_reader/main.py

# --- Tự khởi động lại khi lỗi ---
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
"
    echo "$service_file_content" | sudo tee /etc/systemd/system/gateway.service
    
    sudo systemctl daemon-reload
    sudo systemctl enable gateway.service
    sudo systemctl start gateway.service
    echo "Systemd unit file created and service started."
}

create_systemd_service
echo "Finish setting up the environment"
