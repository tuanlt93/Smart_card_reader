#include <SPI.h>
#include <MFRC522.h>
#include <esp_task_wdt.h>

/* ── Chân kết nối RC522 với ESP32 ─────────────── */
#define SS_PIN 5   // SDA / SS
#define RST_PIN 22  // RST
#define LED_BUILTIN 2

// VCC ↔ 3V3
// GND ↔ GND
// SCK ↔ GPIO18
// MOSI ↔ GPIO23
// MISO ↔ GPIO19
// SS/CS ↔ GPIO5

/* ── Tham số ─────────────────────────────────── */
constexpr uint32_t CARD_REMOVED_TIMEOUT_MS  = 1000;
constexpr uint32_t EMPTY_CYCLE_RESET_CNT    = 200;
constexpr int MAX_RETRY_CONNECT_RC522       = 5;
constexpr uint32_t TIMEOUT_MS_CONNECT_RC522 = 2000;


MFRC522 rfid(SS_PIN, RST_PIN);

/* Biến chương trình */
byte currentUid[10];
byte currentUidSize = 0;

uint32_t lastCardSeen  = 0;
uint32_t emptyCycleCnt = 0;


/* ── SETUP ───────────────────────────────────── */
void setup() {
  Serial.begin(115200);
  SPI.begin();        // ESP32: SCK=18, MISO=19, MOSI=23, SS=5 (theo wiring ở trên)
  SPI.setFrequency(1000000);         // ↓ đặt 1 MHz

  delay(50);
  
  pinMode(LED_BUILTIN, OUTPUT);
  initReader();  // thử tối đa 5 lần, sau đó restart ESP32 nếu thất bại

  // Cấu hình WDT
  esp_task_wdt_config_t twdt_config = {
    .timeout_ms = 10000,  // 10 giây
    .idle_core_mask = (1 << portNUM_PROCESSORS) - 1, // giám sát tất cả core
    .trigger_panic = true, // reset nếu timeout
  };

  // Khởi tạo WDT với config trên
  esp_task_wdt_deinit();
  esp_task_wdt_init(&twdt_config);
  esp_task_wdt_add(NULL);   // add task loop (NULL = task hiện tại)

}

void initReader() {
  int retry = MAX_RETRY_CONNECT_RC522;
  while (retry-- > 0) {
    Serial.println(F("nitializing RC522..."));
    
    rfid.PCD_Init();
    rfid.PCD_AntennaOn();
    // rfid.PCD_SetRegisterBitMask(rfid.RFCfgReg, (0x07 << 4)); // tăng độ nhạy

    byte ver = rfid.PCD_ReadRegister(rfid.VersionReg);
    Serial.print(F("RC522 VersionReg: 0x"));
    Serial.println(ver, HEX);

    if (ver == 0xB2 || ver == 0x82 || ver == 0x91 || ver == 0x92) {
      emptyCycleCnt = 0;
      memset(currentUid, 0, sizeof(currentUid));
      currentUidSize = 0;
      return;   // thành công, thoát hàm
    }

    delay(TIMEOUT_MS_CONNECT_RC522);
  }

  // Nếu thử maxRetry lần mà vẫn không thấy RC522
  delay(TIMEOUT_MS_CONNECT_RC522);
  ESP.restart();
}


/* ── LOOP ────────────────────────────────────── */
void loop() {
  esp_task_wdt_reset();   // vỗ WDT mỗi vòng (hoặc ở các điểm an toàn)

  byte uid[10];
  byte uidSize = 0;

  // 1) Thử đọc thẻ
  if (readUid(uid, uidSize)) {

    if (uidSize != currentUidSize || memcmp(uid, currentUid, uidSize) != 0) {
      memcpy(currentUid, uid, uidSize);
      currentUidSize = uidSize;
      printUid(uid, uidSize);
      blinkLed();
    }

    lastCardSeen  = millis();
    emptyCycleCnt = 0;
  }
  /* ── 2. Không thấy thẻ ────────────────────────────────────── */
  else {
    ++emptyCycleCnt;

    // 2a) Thẻ vừa bị rút khỏi vùng đọc
    if (emptyCycleCnt > 1 && currentUidSize && millis() - lastCardSeen > CARD_REMOVED_TIMEOUT_MS) {
      Serial.println(F("removed"));
      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();
      currentUidSize = 0;
    }

    // 2b) Reset module nếu lâu không có thẻ
    if (emptyCycleCnt > EMPTY_CYCLE_RESET_CNT) {
      softResyncRC522();
    }
  }

  delay(150);   // vòng lặp nhàn CPU, ~80ms/chu kỳ
}

/* ── Hàm tiện ích ────────────────────────────── */
bool readUid(byte* uid, byte &len) {
  if (!rfid.PICC_IsNewCardPresent()) return false;
  if (!rfid.PICC_ReadCardSerial())   return false;

  // Kiểm tra độ dài UID hợp lệ
  if (!(rfid.uid.size == 4 || rfid.uid.size == 7 || rfid.uid.size == 10)) {
    rfid.PICC_HaltA();
    return false;
  }

  // Copy UID
  len = rfid.uid.size;
  memcpy(uid, rfid.uid.uidByte, len);

  return true;
}

void printUid(const byte *uid, byte len) {
  char uidStr[16];
  int pos = 0;

  for (byte i = 0; i < len; i++) {
    // mỗi lần ghi thêm 2 ký tự HEX, kèm ký tự kết thúc
    pos += snprintf(&uidStr[pos], sizeof(uidStr) - pos, "%02X", uid[i]);
  }
  Serial.println(uidStr);
}

void resetReader() {
  Serial.println(F("Reset RC522..."));
  rfid.PCD_Init();
  rfid.PCD_AntennaOn();
  rfid.PCD_SetRegisterBitMask(rfid.RFCfgReg, (0x07 << 4)); // tăng độ nhạy
  emptyCycleCnt = 0;
}

void blinkLed() {
  digitalWrite(LED_BUILTIN, HIGH);  // turn the LED on 
  delay(150);                      // wait for a second
  digitalWrite(LED_BUILTIN, LOW);   // turn the LED off 
}

void softResyncRC522() {
  Serial.println(F("Reset RC522..."));
  // 1) Dừng crypto và đưa state máy về IDLE
  // rfid.PCD_StopCrypto1();  // clear MFCrypto1On (Status2Reg)

  // 2) Clear IRQ + flush FIFO + về framing mặc định
  rfid.PCD_WriteRegister(rfid.CommandReg, rfid.PCD_Idle);
  rfid.PCD_WriteRegister(rfid.ComIrqReg, 0x7F);    // clear all IRQ flags
  rfid.PCD_WriteRegister(rfid.FIFOLevelReg, 0x80); // flush FIFO
  rfid.PCD_WriteRegister(rfid.BitFramingReg, 0x00);
  rfid.PCD_WriteRegister(rfid.CollReg, 0x80);      // reset bit collision

  // 3) (tuỳ chọn) Re-apply vài tham số timing/ASK nếu bạn đã tinh chỉnh
  // rfid.PCD_WriteRegister(rfid.TModeReg, 0x80);       // TAuto=1
  // rfid.PCD_WriteRegister(rfid.TPrescalerReg, 0xA9);  // ~40kHz
  // rfid.PCD_WriteRegister(rfid.TReloadRegH, 0x03);
  // rfid.PCD_WriteRegister(rfid.TReloadRegL, 0xE8);
  // rfid.PCD_WriteRegister(rfid.TxASKReg, 0x40);       // 100% ASK
  // rfid.PCD_WriteRegister(rfid.ModeReg, 0x3D);

  // 4) Đảm bảo anten đang bật + gain như trước
  rfid.PCD_AntennaOn();  // chỉ bật nếu chưa bật, không “đập” lại field
  rfid.PCD_SetRegisterBitMask(rfid.RFCfgReg, (0x07 << 4)); // giữ độ nhạy

  // 5) (tuỳ chọn) chờ 1–2 ms cho analog settle nếu vừa flush nhiều
  emptyCycleCnt = 0;
  delay(2);
}


