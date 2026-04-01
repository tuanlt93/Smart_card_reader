# Smart_card_reader
sudo nano /boot/firmware/config.txt

### Giảm gpu_mem xuống 128 (đối với Pi 3B 1GB RAM là đủ, 256 dễ gây treo máy)
gpu_mem=128

### Cấu hình CMA cực kỳ quan trọng cho driver KMS trên Pi cũ
dtoverlay=vc4-kms-v3d,cma-256