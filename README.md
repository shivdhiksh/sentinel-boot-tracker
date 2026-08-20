# 🛡️ Sentinel Boot Tracker

A lightweight, intelligent Windows laptop power and activity monitoring system that delivers real-time **Telegram notifications** enriched with native Windows Geolocation, battery telemetry, and session activity (Startup, Shutdown, Lock, and Unlock).

---

## 🚀 Project Overview

**Sentinel Boot Tracker** (v0.3 — *Sentinel Intelligence*) combines low-overhead Windows automation with a 3-tier telemetry engine to provide instant situational awareness whenever your laptop boots, locks, unlocks, or initiates a shutdown.

```text
  Windows Laptop (ASUS TUF A15)
               │
      ┌────────┼────────┬────────┐
      ▼        ▼        ▼        ▼
   Startup    Lock   Unlock   Shutdown (Event 1074)
      │        │        │        │
      ▼        └────┬───┘        ▼
Task Scheduler      │       Task Scheduler (SYSTEM)
 (User Login)       ▼            │
      │       session_monitor    │
      └─────────────┼────────────┘
                    ▼
            silent_runner.vbs
                    │
                    ▼
            power_monitor.py
                    │
                    ▼
            sentinel/ package
   ├── location (3-Tier Windows Geolocation + 1h Cache)
   ├── session_monitor (Native Win32 WTSSessionNotification)
   ├── system_info (OS, User, Battery %, AC Status)
   ├── network (Public IP Detection & IP Geolocation)
   └── telegram (Retry Loops & Rich HTML Formatting)
                    │
                    ▼
             Telegram Bot API
                    │
                    ▼
           📱 Telegram Notification
```

---

## ✨ Features

### 📍 3-Tier Multi-Source Geolocation Engine (New in v0.3)
* **Tier 1 — Windows Native Geolocation:** Queries `Windows.Devices.Geolocation` via WinRT in active user sessions. Captures live `PositionSource` (`Wi-Fi`, `Cellular`, `Satellite/GNSS`), exact horizontal accuracy in meters (e.g. `~112 m`), and generates verified Google Maps links.
* **Tier 2 — User-Session Location Cache (`.location_cache.json`):** Persists the last verified native location for background processes running in Session 0 (such as the SYSTEM shutdown task).
  * **Strict 1-Hour Expiration:** Cache expires after 3600 seconds.
  * **Explicit Telemetry State:** Never claims cached data is live; clearly displays `🟡 Status: Cached location` and `🕒 Location updated: X minutes ago`.
* **Tier 3 — Multi-Provider IP Fallback:** If Windows location is disabled, denied, or offline and no fresh cache exists, automatically falls back to IP geolocation (`ipapi.co` $\rightarrow$ `ip-api.com` $\rightarrow$ `ipify.org`), accurately labeled as `📍 APPROXIMATE LOCATION` with `⚠️ IP-based location is not precise.`

### 🔒 Workstation Lock & Unlock Monitoring (New in v0.3)
* **Native Win32 Session Events:** Uses `WTSRegisterSessionNotification` on `WM_WTSSESSION_CHANGE` to detect workstation locks (`Win+L`) and unlocks.
* **Zero Polling:** Pure Windows event loop; consumes 0% CPU when idle with built-in deduplication.

### 🔋 Battery & System Telemetry
* Real-time battery percentage tracking and AC power state detection (`AC` vs `Battery`).
* Captures Windows OS version, active user, device hostname, and Python runtime.

### 🛡️ Security & Privacy
* **Zero Secret Exposure:** Bot tokens are automatically redacted from error logs (`[REDACTED_TOKEN]`).
* **Untracked Private Assets:** `.env`, `error.log`, and `.location_cache.json` are strictly ignored by `.gitignore`.
* **Zero Bloat / Privacy Respect:** Sentinel collects only high-level device metrics and hardware status. No passwords, keystrokes, browser history, or private files are ever accessed.

---

## 🪟 Windows Location Services Setup

To enable Tier 1 high-accuracy location via Wi-Fi triangulation:
1. Open **Windows Settings** (`Win + I`).
2. Navigate to **Privacy & Security** $\rightarrow$ **Location**.
3. Turn **Location services** **ON**.
4. Enable **Let apps access your location** and **Let desktop apps access your location**.

> [!NOTE]
> If Windows Location Services is disabled or permission is not granted, Sentinel operates with zero crashes and gracefully falls back to Tier 3 IP Geolocation.

---

## 🏗️ Project Architecture

```text
sentinel-boot-tracker/
│
├── sentinel/                     # Modular Sentinel Engine
│   ├── __init__.py               # Package metadata and version info (0.3.0)
│   ├── config.py                 # Environment variables, logging, token sanitization
│   ├── location.py               # 3-Tier Geolocation Engine & 1h cache manager
│   ├── session_monitor.py        # Win32 WTSRegisterSessionNotification daemon
│   ├── system_info.py            # Battery status, OS, username, and device info
│   ├── network.py                # Public IP detection & multi-provider IP fallback
│   ├── notifications.py          # HTML message builder with event & tier rendering
│   └── telegram.py               # Telegram API client with resilient retry loops
│
├── power_monitor.py              # CLI entry point (supports startup, shutdown, lock, unlock, session_monitor)
├── silent_runner.vbs             # Silent VBScript wrapper for background execution
├── requirements.txt              # Dependencies (requests, python-dotenv, psutil, winrt)
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git exclusion rules
│
├── .env                          # Local credentials (NEVER committed)
├── .location_cache.json          # Local location cache (NEVER committed)
└── error.log                     # Local error logs (NEVER committed)
```

---

## ⚙️ Requirements

* **Operating System:** Windows 10 / 11 (64-bit)
* **Python:** Python 3.13+ (or 3.10+)
* **Dependencies:** `requests`, `python-dotenv`, `psutil`, `winrt-Windows.Devices.Geolocation`, `winrt-Windows.Foundation`
* **Accounts:** Telegram account and a Telegram Bot token via BotFather

---

## 📦 Installation

```powershell
git clone https://github.com/shivdhiksh/sentinel-boot-tracker.git
cd sentinel-boot-tracker
py -m pip install -r requirements.txt
```

Create `.env` based on `.env.example`:
```env
TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
```

---

## 🧪 Testing & Execution

### 1. Standalone Location Diagnostic Test (No Telegram Messages)
```powershell
py -m sentinel.location
```
*Output demonstrates real-time location tier, accuracy, source, and cache status.*

### 2. Manual Power & Session Alert Tests
* **Startup Alert:** `py power_monitor.py startup`
* **Shutdown Alert:** `py power_monitor.py shutdown`
* **Lock Alert:** `py power_monitor.py lock`
* **Unlock Alert:** `py power_monitor.py unlock`

### 3. Silent Wrapper Execution
* **Silent Startup:** `wscript silent_runner.vbs startup`
* **Silent Shutdown:** `wscript silent_runner.vbs shutdown`

### 4. Background Session Monitor Daemon
```powershell
py power_monitor.py session_monitor
```
*Listens for live `Win+L` lock and unlock events in real-time.*

---

## 📸 Telegram Alert Samples

### 🚀 Live Windows Wi-Fi Location (Startup)
```text
🚀 SENTINEL ALERT — SYSTEM STARTUP
━━━━━━━━━━━━━━━━━━━━━━
💻 Device: ASUS TUF A15 (ASUSTUFGAMING)
🪟 OS: Windows 11
👤 User: koppu
🕒 Time: 2026-08-20 03:25:00 PM

🔋 Battery: 70%
⚡ Power: Battery

🌐 Public IP: 2401:4900:cbe9:xxxx:xxxx:xxxx:xxxx:xxxx

📍 LOCATION
Latitude: 17.396335
Longitude: 78.517847

🎯 Accuracy: ~112 m
📡 Source: Wi-Fi
🟢 Status: Live location

🗺️ Google Maps:
https://www.google.com/maps?q=17.396335,78.517847
━━━━━━━━━━━━━━━━━━━━━━
✅ Status: Event triggered and confirmed
```

### 🛑 Fresh Cached Location (SYSTEM Shutdown)
```text
🛑 SENTINEL ALERT — SYSTEM SHUTDOWN
━━━━━━━━━━━━━━━━━━━━━━
💻 Device: ASUS TUF A15 (ASUSTUFGAMING)
🪟 OS: Windows 11
👤 User: SYSTEM
🕒 Time: 2026-08-20 03:30:00 PM

🔋 Battery: 68%
⚡ Power: Battery

🌐 Public IP: 2401:4900:cbe9:xxxx:xxxx:xxxx:xxxx:xxxx

📍 LOCATION
Latitude: 17.396335
Longitude: 78.517847

🎯 Accuracy: ~112 m
📡 Source: Wi-Fi
🕒 Location updated: 5 minutes ago
🟡 Status: Cached location

🗺️ Google Maps:
https://www.google.com/maps?q=17.396335,78.517847
━━━━━━━━━━━━━━━━━━━━━━
⚡ Status: Shutdown initiated
```

### 📍 IP Geolocation Fallback (When Location is Disabled / Cache > 1h)
```text
📍 APPROXIMATE LOCATION
Hyderabad, Telangana, India

🎯 Accuracy: Approximate
📡 Source: IP address
⚠️ IP-based location is not precise.

🗺️ Google Maps:
https://www.google.com/maps?q=17.375289,78.47439
```

---

## 🪟 Windows Automation Reference

| Event | Task / Runner | Trigger | Context | Action |
| :--- | :--- | :--- | :--- | :--- |
| **Startup** | `TUF Power Monitor - Startup` | User Logon | User Session | `wscript.exe silent_runner.vbs startup` |
| **Shutdown** | `TUF Power Monitor - Shutdown` | Event 1074 | `NT AUTHORITY\SYSTEM` | `wscript.exe silent_runner.vbs shutdown` |
| **Session** | `sentinel.session_monitor` | Background Task / Logon | User Session | `wscript.exe silent_runner.vbs session_monitor` |

---

## 👨‍💻 Author

**Shiva Dhikshith**  
* GitHub: [@shivdhiksh](https://github.com/shivdhiksh)  
* LinkedIn: [@shivdhiksh](https://www.linkedin.com/in/shivdhiksh)

---

*Licensed for educational and personal use.*
