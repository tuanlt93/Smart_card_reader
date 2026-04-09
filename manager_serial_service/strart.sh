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

# --- User / quyền ---
User=tuanlt
Group=tuanlt
# Nếu bạn đã tạo /dev/device0 với MODE=0660 GROUP=dialout
SupplementaryGroups=dialout

# --- Thư mục & lệnh chạy ---
WorkingDirectory=/home/tuanlt/Smart_card_reader/manager_serial_service
ExecStart=/home/tuanlt/Smart_card_reader/venv/bin/python3 /home/tuanlt/Smart_card_reader/manager_serial_service/main.py

# --- Tự khởi động lại khi lỗi ---
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
"
    echo "$service_file_content" | sudo tee /etc/systemd/system/manager_serial.service
    
    sudo systemctl daemon-reload
    sudo systemctl enable manager_serial.service
    sudo systemctl start manager_serial.service
    echo "Systemd unit file created and service started."
}

create_systemd_service
echo "Finish setting up the environment"
