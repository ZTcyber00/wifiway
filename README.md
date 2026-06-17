<div align="center">

```
██╗    ██╗██╗███████╗██╗    ██╗ █████╗ ██╗   ██╗
██║    ██║██║██╔════╝██║    ██║██╔══██╗╚██╗ ██╔╝
██║ █╗ ██║██║█████╗  ██║ █╗ ██║███████║ ╚████╔╝ 
██║███╗██║██║██╔══╝  ██║███╗██║██╔══██║  ╚██╔╝  
╚███╔███╔╝██║██║     ╚███╔███╔╝██║  ██║   ██║   
 ╚══╝╚══╝ ╚═╝╚═╝      ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝  
```

# wifway

**Wi-Fi ağ güvenlik test ve analiz aracı — Python 3 / Linux**

![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python)
![Platform](https://img.shields.io/badge/Platform-Linux-green?style=flat-square&logo=linux)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

</div>

---

## ⚠️ Yasal Uyarı

Bu araç yalnızca **kendi ağınızda** veya **yetkili penetrasyon testi ortamlarında** kullanım içindir.  
İzinsiz kullanım Türkiye'de ve pek çok ülkede **yasadışıdır.**  
Tüm sorumluluk kullanıcıya aittir.

---

## 📋 Özellikler

### 1. Ağ Hedefli Saldırılar
| Özellik | Açıklama | Gerekli Araç |
|---|---|---|
| Deauth (Tekil) | Belirli bir cihazın bağlantısını keser | aircrack-ng |
| Deauth (Tüm Ağ) | Ağdaki tüm cihazları sürekli koparır | aircrack-ng |
| Toplu Deauth | Aynı anda birden fazla ağa saldırı | aircrack-ng |
| Handshake Yakalama | WPA/WPA2 handshake + aircrack/hashcat kırma | aircrack-ng, hashcat |
| Evil Twin | Sahte AP + Captive Portal şifre yakalama | hostapd, dnsmasq |
| WPS PIN Saldırısı | Normal brute-force veya Pixie Dust | reaver |
| PMKID Saldırısı | İstemci beklemeden hash yakalama | hcxdumptool, hcxtools |
| WPA Enterprise | Sahte RADIUS ile kurumsal ağ hash yakalama | hostapd-wpe |

### 2. Keşif & Analiz
| Özellik | Açıklama | Gerekli Araç |
|---|---|---|
| OS Fingerprinting | Cihaz işletim sistemi tespiti | nmap |
| Probe Request Dinleme | Cihaz ağ geçmişi tespiti | tshark |
| ARP Spoofing / MITM | Ağ trafiğini araya girme | arpspoof (dsniff) |
| SSL Stripping | HTTPS → HTTP düşürme | sslstrip |
| CVE / Zafiyet Tarama | nmap NSE scriptleri ile CVE tespiti | nmap |
| Bluetooth Tarama | Klasik BT + BLE + L2Ping | bluez |
| Kanal Atlama | Tüm kanalları tarama | aircrack-ng |

### 3. Ağ Bağımsız Araçlar
| Özellik | Açıklama | Gerekli Araç |
|---|---|---|
| Beacon Flood | Sahte ağ yayını (artan/sabit/rastgele) | mdk4 |
| MAC Spoofing | MAC adresi değiştirme / geri alma | iproute2, macchanger |
| Wordlist Üretici | Hedefe özel akıllı wordlist | crunch (opsiyonel) |

### 4. Diğer
| Özellik | Açıklama |
|---|---|
| Otomasyon Modu | Seçilen adımları sırayla otomatik çalıştırır |
| Veri Yönetimi | Tarama dosyalarını listele / sil |
| Tarama Geçmişi | Önceki taramaları kaydet ve yükle |
| Bildirimler | Telegram / Discord anlık bildirim |
| JSON Loglama | Tüm işlemleri tarihli JSON dosyasına kaydeder |

---

## 🖥️ Gereksinimler

### İşletim Sistemi
- Linux (Kali, Parrot, Ubuntu)
- Monitor modu destekleyen Wi-Fi kartı

### Sistem Araçları
```bash
sudo apt install -y \
  aircrack-ng xterm hostapd dnsmasq reaver mdk4 nmap \
  tshark dsniff sslstrip hcxdumptool hcxtools hashcat \
  macchanger crunch bluez btscanner hostapd-wpe
```

### Python Paketleri
```bash
pip install -r requirements.txt
```

---

## 🚀 Kurulum & Çalıştırma

```bash
git clone https://github.com/ZTcyber00/wifiway.git
cd wifway
pip install -r requirements.txt
sudo python3 wifi_scanner.py
```

---

## 📁 Dosya Yapısı

```
wifway/
├── wifi_scanner.py       # Ana script
├── requirements.txt      # Python bağımlılıkları
├── README.md
├── LICENSE
└── .gitignore

# Çalışma sırasında oluşan klasörler (git'e gitmez):
scan_results/
├── scan_capture-01.csv          # Ağ taramaları
├── hs_AA_BB_CC_DD_EE_FF-01.cap  # Handshake dosyaları
├── pmkid_*.pcapng               # PMKID yakalamalar
├── custom_wordlist.txt          # Üretilen wordlist
└── scan_history.json            # Tarama geçmişi

logs/
└── wifway_2025-01-01.json       # Günlük log
```

---

## 🗺️ Kullanım Akışı

```
Ana Menü
├── 1. Ağ Hedefli Saldırılar
│     └── Yeni Tara / Geçmişten Yükle → Ağ Seç → İstemci Tara → Saldırı
├── 2. Keşif & Analiz
│     └── Araç Seç → (gerekiyorsa Tara) → Çalıştır
├── 3. Ağ Bağımsız Araçlar
│     └── Direkt çalıştır
├── 4. Otomasyon Modu
├── 5. Veri Yönetimi
├── 6. Bildirim Ayarları
└── ?  Yardım (tüm seçeneklerin açıklaması)
```

---

## ⌨️ Kısayollar

| Tuş | Eylem |
|---|---|
| `?` | Herhangi bir menüde yardım |
| `0` | Geri dön |
| `Ctrl+C` | Çıkış (güvenli kapatma) |

---

## 📦 Bağımlılıklar

| Paket | Versiyon | Açıklama |
|---|---|---|
| rich | ≥ 13.0.0 | Terminal arayüzü |
| requests | ≥ 2.28.0 | Telegram/Discord bildirimleri |

---

## 📄 Lisans

MIT License — bkz. [LICENSE](LICENSE)

---

<div align="center">
<sub>Yalnızca eğitim ve yetkili penetrasyon testi amaçlıdır.</sub>
</div>
