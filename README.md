# 🛡️ Sentinel Boot Tracker

A lightweight, intelligent Windows laptop power and activity monitoring system that sends real-time **Telegram notifications** enriched with network, battery, and approximate location telemetry upon system startup and shutdown.

---

## 🚀 Project Overview

**Sentinel Boot Tracker** (v0.3 — *Sentinel Intelligence*) monitors Windows power events and delivers rich telemetry alerts directly to your Telegram.

It pairs low-overhead Windows automation with resilient Python telemetry collection to provide instant situational awareness whenever your laptop boots up or initiates a shutdown.

```text
  Windows Laptop (ASUS TUF A15)
               │
      ┌────────┴────────┐
      ▼                 ▼
   Startup          Shutdown (Event 1074)
      │                 │
      ▼                 ▼
 Task Scheduler    Task Scheduler (SYSTEM)
      │                 │
      └────────┬────────┘
               ▼
       silent_runner.vbs
               │
               ▼
       power_monitor.py
               │
               ▼
       sentinel/ package
   ├── system_info (OS, User, Battery %)
   ├── network (Public IP, Approx Location)
   └── telegram (Retry loops, HTML formatting)
               │
               ▼
        Telegram Bot API
               │
               ▼
      📱 Telegram Notification
```

---

## ✨ Features

### 🚀 Sentinel v0.3 Intelligence (New)
* 🌐 **Public IP Detection:** Automated multi-provider IP resolution (`ipapi.co` $\rightarrow$ `ip-api.com` $\rightarrow$ `ipify.org`).
* 📍 **Approximate Geolocation:** City, Region, and Country mapping based on public IP routing.
* 🗺️ **Dynamic Google Maps Link:** Direct map coordinates URL generated when latitude/longitude coordinates are available.
* 🔋 **Battery & Power Telemetry:** Real-time battery percentage tracking and AC adapter status (`AC` vs `Battery`).
* 💻 **System Metadata:** Gathers device hostname, Windows version, active username, and Python runtime version.
* 🏛️ **Modular Package Architecture:** Clean separation of concerns into a dedicated `sentinel/` package while maintaining seamless entry-point compatibility.

### 🛡️ Core Reliability & Security Baseline
* 🤖 **Telegram Bot API Integration:** Instant alerts with rich HTML formatting and emoji indicators.
* 🔕 **Silent Background Execution:** Zero-console popup wrapper using Windows VBScript (`wscript.exe`).
* 🪟 **Automated Event Triggers:**
  * **Startup:** Automatic execution on Windows user login via Windows Task Scheduler.
  * **Shutdown:** Automatic execution on Windows Event ID 1074 (User32 shutdown) running with SYSTEM privileges.
* 🌐 **Network Resilience:** Multi-attempt retry mechanisms (up to 10 attempts for startup, 3 for shutdown) with backoff intervals to handle delayed Wi-Fi connections.
* 🔒 **Token Sanitization:** Automatically redacts sensitive Telegram Bot tokens from error logs and console outputs.
* 🔐 **Secure Credential Isolation:** All secrets reside in local `.env` files strictly excluded from source control.

---

## 📍 Approximate Location Notice

> [!NOTE]
> Standard laptops do not possess built-in hardware GPS receivers. All location telemetry is derived from **Public IP Geolocation** provided by upstream network routing tables and ISPs.
> 
> * Location data is labeled strictly as **"Approximate Location"**.
> * If IP geolocation fails or is unreachable, the core notification continues to dispatch gracefully with `Unavailable` markers.

---

## 🏗️ Project Architecture

```text
sentinel-boot-tracker/
│
├── sentinel/                     # Modular Sentinel Engine
│   ├── __init__.py               # Package metadata and version info (0.3.0)
│   ├── config.py                 # Environment variables, logging, token sanitization
│   ├── system_info.py            # Battery status, OS, username, and device info
│   ├── network.py                # Public IP detection & approximate IP geolocation
│   ├── notifications.py          # HTML message builder and visual formatters
│   └── telegram.py               # Telegram API client with resilient retry loops
│
├── power_monitor.py              # CLI entry point (preserves legacy interface)
├── silent_runner.vbs             # Silent VBScript wrapper for background execution
├── requirements.txt              # Python package dependencies
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git exclusion rules
│
├── .env                          # Local credentials (NEVER committed)
└── error.log                     # Local error logs (NEVER committed)
```

---

## ⚙️ Requirements

* **Operating System:** Windows 10 / 11 (64-bit)
* **Python:** Python 3.13+ (or 3.10+)
* **Dependencies:** `requests`, `python-dotenv`, `psutil`
* **Accounts:** Telegram account and a Telegram Bot token via BotFather

---

## 📦 Installation & Setup

1. **Clone the Repository:**
   ```powershell
   git clone https://github.com/shivdhiksh/sentinel-boot-tracker.git
   cd sentinel-boot-tracker
   ```

2. **Install Dependencies:**
   ```powershell
   py -m pip install -r requirements.txt
   ```

3. **Configure Environment Credentials:**
   Create a `.env` file in the project root based on `.env.example`:
   ```env
   TELEGRAM_BOT_TOKEN="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
   TELEGRAM_CHAT_ID="987654321"
   ```

---

## 🧪 Testing & Execution

### 1. Direct Python Testing
Run manual tests from PowerShell or Command Prompt:

* **Startup Notification:**
  ```powershell
  py power_monitor.py startup
  ```

* **Shutdown Notification:**
  ```powershell
  py power_monitor.py shutdown
  ```

### 2. Silent Runner Testing
Test the VBScript wrapper to verify execution without opening a console window:

* **Silent Startup:**
  ```powershell
  wscript silent_runner.vbs startup
  ```

* **Silent Shutdown:**
  ```powershell
  wscript silent_runner.vbs shutdown
  ```

---

## 📸 Telegram Alert Samples

### 🚀 Startup Alert
```text
🚀 SENTINEL ALERT — SYSTEM STARTUP
━━━━━━━━━━━━━━━━━━━━━━
💻 Device: ASUS TUF A15 (ASUSTUFGAMING)
🪟 OS: Windows 11
👤 User: koppu
🕒 Time: 2026-08-20 03:15:54 PM

🔋 Battery: 70%
⚡ Power: Battery

🌐 Public IP: 2401:4900:cbe9:xxxx:xxxx:xxxx:xxxx:xxxx

📍 Approximate Location:
Hyderabad, Telangana, India

🧭 Coordinates:
17.37529, 78.47439

🗺️ Map:
https://www.google.com/maps?q=17.375289,78.47439
━━━━━━━━━━━━━━━━━━━━━━
✅ Status: Event triggered and confirmed
```

### 🛑 Shutdown Alert
```text
🛑 SENTINEL ALERT — SYSTEM SHUTDOWN
━━━━━━━━━━━━━━━━━━━━━━
💻 Device: ASUS TUF A15 (ASUSTUFGAMING)
🪟 OS: Windows 11
👤 User: koppu
🕒 Time: 2026-08-20 03:15:55 PM

🔋 Battery: 70%
⚡ Power: Battery

🌐 Public IP: 2401:4900:cbe9:xxxx:xxxx:xxxx:xxxx:xxxx

📍 Approximate Location:
Hyderabad, Telangana, India

🧭 Coordinates:
17.37529, 78.47439

🗺️ Map:
https://www.google.com/maps?q=17.375289,78.47439
━━━━━━━━━━━━━━━━━━━━━━
⚡ Status: Shutdown initiated
```

---

## 🪟 Windows Task Scheduler Integration

| Event | Task Name | Trigger | User Account | Action |
| :--- | :--- | :--- | :--- | :--- |
| **Startup** | `TUF Power Monitor - Startup` | At log on of any user | Standard User / Administrator | `wscript.exe "C:\path\to\silent_runner.vbs" startup` |
| **Shutdown** | `TUF Power Monitor - Shutdown` | Event 1074 (User32) | `NT AUTHORITY\SYSTEM` (Highest Privileges) | `wscript.exe "C:\path\to\silent_runner.vbs" shutdown` |

---

## 🔐 Security & Privacy

* **Zero Credential Leaks:** `.env` and `error.log` are strictly ignored by `.gitignore`.
* **Automated Log Sanitization:** Any exception traceback or logging output containing the Telegram token has the secret stripped before writing to disk.
* **Privacy Conscious:** Sentinel collects only high-level device status (OS, username, battery, network routing location). It does not access private files, keystrokes, or browser history.

---

## 🗺️ Project Roadmap

* [x] **Version 0.1 — Core Monitoring**
  * Python notification engine, Telegram integration, environment configuration, silent execution.
* [x] **Version 0.2 — Power Event Automation**
  * Task Scheduler shutdown Event ID 1074 automation running as SYSTEM, login startup trigger.
* [x] **Version 0.3 — Sentinel Intelligence** *(Current Release)*
  * Modular package structure, public IP resolution, approximate geolocation, Google Maps integration, battery telemetry, and extended system info.
* [ ] **Version 0.4 — Advanced Event Detection**
  * Windows Sleep/Wake event detection, restart categorization, Wi-Fi SSID tracking.
* [ ] **Version 1.0 — Sentinel Complete**
  * Automated 1-click Windows installer, SQLite event history database, and local monitoring dashboard.

---

## 👨‍💻 Author

**Shiva Dhikshith**  
* GitHub: [@shivdhiksh](https://github.com/shivdhiksh)  
* LinkedIn: [@shivdhiksh](https://www.linkedin.com/in/shivdhiksh)

---

*Licensed for educational and personal use.*
