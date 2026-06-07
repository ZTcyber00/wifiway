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

**Wi-Fi ağ tarama, analiz ve güvenlik test aracı**

![Python](https://img.shields.io/badge/Python-3.8+-blue?style=flat-square&logo=python)
![Platform](https://img.shields.io/badge/Platform-Linux-green?style=flat-square&logo=linux)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

</div>

---

## ⚠️ Yasal Uyarı

Bu araç yalnızca **kendi ağınızda** veya **yazılı izin aldığınız ortamlarda** kullanılabilir.  
İzinsiz kullanım birçok ülkede **yasadışıdır**. Tüm sorumluluk kullanıcıya aittir.

---

## 📋 Özellikler

### 1. Ağ Hedefli Saldırılar
| Özellik | Açıklama |
|---|---|
| Deauth (Tekil) | Belirli bir istemcinin bağlantısını keser |
| Deauth (Tüm Ağ) | Ağdaki tüm cihazların bağlantısını keser |
| Handshake Yakalama | WPA/WPA2 handshake yakalar, opsiyonel wordlist kırma |
| Evil Twin | Hedef ağın kopyasını oluşturur (hostapd + dnsmasq) |
| WPS PIN Saldırısı | Normal brute-force veya Pixie Dust (reaver) |

### 2. Keşif & Analiz
| Özellik | Açıklama |
|---|---|
| OS Fingerprinting | Ağdaki cihazların işletim sistemini tespit eder (nmap) |

### 3. Ağ Bağımsız Araçlar
| Özellik | Açıklama |
|---|---|
| Beacon Flood | Sahte ağ yayını — artan isimler, sabit liste veya rastgele |

---

## 🖥️ Gereksinimler

### Sistem Araçları
```bash
sudo apt install aircrack-ng xterm hostapd dnsmasq reaver mdk4 nmap -y
```

### Python Paketleri
```bash
pip install -r requirements.txt
```

---

## 🚀 Kurulum

```bash
git clone https://github.com/kullaniciadi/wifway.git
cd wifway
pip install -r requirements.txt
sudo python3 wifi_scanner.py
```

---

## 📁 Dosya Yapısı

```
wifway/
├── wifi_scanner.py     # Ana script
├── requirements.txt    # Python bağımlılıkları
└── README.md           # Bu dosya
```

Tarama sonuçları otomatik olarak `scan_results/` klasöründe birikir:
```
scan_results/
├── scan_capture-01.csv
├── AA_BB_CC_DD_EE_FF_client_scan-01.csv
└── hs_AA_BB_CC_DD_EE_FF-01.cap
```

---

## 🗺️ Kullanım Akışı

```
Program Başlar
└── Ana Menü
    ├── 1. Ağ Hedefli Saldırılar
    │     └── Ağ Tara → Seç → İstemci Tara → Saldırı Seç
    ├── 2. Keşif & Analiz
    │     └── Araç Seç → Ağ Tara → Seç → Çalıştır
    └── 3. Ağ Bağımsız Araçlar
          └── Araç Seç → Direkt Çalıştır
```

---

## 📦 Python Bağımlılıkları

| Paket | Versiyon |
|---|---|
| rich | ≥ 13.0.0 |

---

<div align="center">
<sub>Yalnızca eğitim ve yetkili test amaçlıdır.</sub>
</div>
