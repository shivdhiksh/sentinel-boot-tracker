# 🛡️ Sentinel Boot Tracker

A lightweight, intelligent Windows laptop power and activity monitoring system that delivers real-time **Telegram notifications** enriched with native Windows Geolocation, battery telemetry, session activity (Startup, Shutdown, Lock, and Unlock), and a **secure Telegram remote command engine** (Sentinel v0.5).

---

## 🚀 Project Overview

**Sentinel Boot Tracker** (v0.5 — *Sentinel Command & Telemetry Suite*) combines low-overhead Windows automation with a 3-tier telemetry engine and a modular, strictly authorized remote command engine.

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
   ├── command_engine (Telegram Polling, Router & Deduplication)
   ├── command_auth (Strict Single-User Chat & Interactive Session Gate)
   ├── command_audit (Sanitized Structured Audit Trail)
   ├── system_actions (CPU, RAM, Disk, Battery, Uptime, System Overview)
   ├── security_actions (Sessions, Security Posture, Events, Audit, Health)
   ├── power_actions (Lock, 2-Step Confirmed Shutdown & Restart)
   ├── file_actions (Restricted Approved-Root Find, List, Fileinfo, Open)
   ├── network_actions (Ping Latency, Public IP, Interfaces, Wi-Fi Telemetry)
   ├── agent_actions (Process Diagnostics & Decoupled Safe Restart)
   ├── location (3-Tier Windows Geolocation + 1h Cache)
   ├── session_monitor (Native Win32 WTSSessionNotification Daemon)
   ├── system_info (OS, User, Battery %, AC Status)
   ├── network (Public IP Detection & IP Geolocation)
   └── telegram (Retry Loops & Rich HTML Formatting)
                    │
                    ▼
             Telegram Bot API
                    │
                    ▼
           📱 Telegram Notification / Remote Control
```

---

## ✨ Features

### 🎮 Secure Remote Command Engine (Sentinel v0.5)

Sentinel provides an allowlisted Telegram remote command engine with zero arbitrary shell execution, strict single-user authorization, update deduplication, and structured auditing.

#### 📊 System Telemetry
* `/status` — Comprehensive device overview, uptime, battery, load, and network state.
* `/cpu` — Live CPU utilization load %, topology (physical/logical cores), and current/max clock speeds.
* `/ram` — RAM utilization %, used/total, available memory, and swap/pagefile status.
* `/disk` — Local fixed drive partitions, total/used/free space in GB, and usage %.
* `/battery` — Detailed battery level, charging/discharging power state, and estimated runtime.
* `/uptime` — Windows uptime duration and exact system boot timestamp.
* `/system` — Safe system summary: Windows edition, architecture, CPU model, total RAM, and GPU models.
* `/network` — Active physical and wireless network adapters, IPv4 addresses, netmasks, link speeds, and public IP.
* `/wifi` — Connected Wi-Fi SSID, signal quality %, radio standard (802.11ax/ac/n), channel, and link rates without exposing credentials.
* `/location` — Multi-tier geolocation (Windows Live GPS $\rightarrow$ 1h cache $\rightarrow$ IP fallback).

#### 🔒 Security & Monitoring
* `/sessions` — Active Windows console session ID, process session ID, and logged-in users.
* `/security` — Sentinel security posture summary: authorization status, deduplication state, allowlist count, interactive session status, and audit trail status.
* `/events` — Recent Sentinel alert and power event history parsed safely from `error.log`.
* `/audit` — Recent remote command audit entries in sanitized format with masked IDs and redacted tokens.
* `/lastboot` — Latest system boot timestamp, device hostname, and uptime.
* `/health` — Component-by-component self check (Bot Token, Chat ID, Telegram API, Storage, State Persistence, Session Context).
* `/version` — Sentinel version manifest (`v0.5.0`), Python runtime, OS, and dependency versions (`psutil`, `requests`, `PySide6`).

#### ⚡ Power Controls
* `/lock` — Instantly locks workstation using native Win32 `LockWorkStation`.
* `/shutdown` — Initiates 2-step shutdown request with a monotonic 30-second confirmation window.
* `/confirm_shutdown` — Confirms pending shutdown from the bound authorized chat within 30 seconds.
* `/restart` — Initiates 2-step restart request with a monotonic 30-second confirmation window.
* `/confirm_restart` — Confirms pending restart from the bound authorized chat within 30 seconds.

#### 📁 Safe File Operations
* `/find <filename>` — Searches strictly within approved roots (`project`, `desktop`, `documents`, `downloads`) with bounded depth (3 levels) and result limits (15 items). Path separators and traversal queries are hard-blocked.
* `/list [approved-folder]` — Lists directory contents strictly within approved roots with file/folder icons and human-readable sizes.
* `/fileinfo <path>` — Returns safe metadata only (name, parent, size, type, creation/modification timestamps). Never reads or exposes file contents or environment secrets.
* `/open <approved-folder>` — Opens an approved folder in Windows Explorer. Gated behind active interactive console session checks; rejects executables, scripts, or non-directories.

#### 📡 Network Diagnostics
* `/ping` — Measures round-trip latency (ms) against trusted predefined endpoints (`1.1.1.1`, `8.8.8.8`, `api.telegram.org`) with a 2.0s bounded socket timeout. Never accepts arbitrary user hosts.
* `/publicip` — Multi-provider public IP detection and approximate geographic region.

#### 🤖 Agent Lifecycle
* `/agent` — Sentinel agent process telemetry: PID, PPID, process start time, uptime, memory RSS, CPU load, and thread count.
* `/restart_agent` — Safely restarts Sentinel daemon by spawning a detached helper process and releasing the single-instance mutex.

#### 📸 Sensory & Interactive
* `/screenshot` — Captures primary display desktop screenshot. Strictly restricted to active interactive console sessions (rejected in Session 0 / SYSTEM context).
* `/processes` — Lists top 20 active processes sorted by RAM usage. Command-line arguments are omitted to prevent credential leaks.
* `/camera` — Captures a single webcam photo automatically once opted in by the laptop owner. Displays a visible on-screen active indicator during capture; no repeated Allow/Deny clicks required. Disabled by default.
* `/help` / `/start` — Comprehensive command reference detailing syntax, confirmation requirements, and security gates.

---

## 🔒 Security Architecture & Boundaries

1. **Strict Single-User Authorization:** Every remote command is validated against `AUTHORIZED_CHAT_ID`. Unauthorized chats receive an immediate access denial and are recorded in the audit trail.
2. **Sanitized Structured Audit Logging:** Every remote action (success, rejection, or failure) is logged to `error.log` with masked chat IDs (`123****89`) and redacted tokens (`[REDACTED_TOKEN]`).
3. **Zero Arbitrary Execution:** No arbitrary shell, PowerShell, `eval`, `exec`, or dynamic command invocation exists anywhere in Sentinel.
4. **Restricted Filesystem Roots:** File operations are strictly locked to approved directories (`BASE_DIR`, `Desktop`, `Documents`, `Downloads`). All paths are resolved canonicalized; directory traversal (`..`) is hard-blocked.
5. **Metadata-Only File Inspection:** `/fileinfo` inspects `os.stat` only. File contents, environment variables, and secrets are never read or transmitted.
6. **2-Step Power State Confirmation:** Both `/shutdown` and `/restart` require 2-step confirmation bound to the requesting chat ID with a monotonic 30-second TTL.
7. **Interactive Console Gating:** Desktop screenshots and camera captures strictly verify `ProcessIdToSessionId != 0` and console session equality (blocks Session 0 / SYSTEM context).
8. **Persistent Local Opt-In for Remote Camera:** `/camera` requires explicit opt-in by the laptop owner via the local CLI (`py power_monitor.py camera-enable`). It is disabled by default. Once opted in, `/camera` automatically captures exactly one frame without per-request popups while always displaying a visible on-screen banner ("🔴 WEBCAM ACTIVE") on the user's desktop. Remote commands cannot enable the camera.
9. **Credential-Safe Wi-Fi Telemetry:** Wi-Fi queries strictly inspect interface telemetry (`netsh wlan show interfaces`). Password exports (`key=clear`) are strictly prohibited.
10. **Single-Instance Mutex & Decoupled Daemon:** Uses native Win32 mutex `SentinelSessionMonitor_<username>` with `CREATE_BREAKAWAY_FROM_JOB` to prevent Task Scheduler premature termination.

---

## 🏗️ Project Architecture

```text
sentinel-boot-tracker/
│
├── sentinel/                     # Modular Sentinel Engine
│   ├── __init__.py               # Package metadata and version info (0.5.0)
│   ├── config.py                 # Configuration, logging, secret redaction, chat masking
│   ├── settings.py               # Local persistent settings (Remote Camera Opt-In)
│   ├── command_engine.py         # Telegram polling, update deduplication & router
│   ├── command_auth.py           # Sender authorization & Win32 console session validation
│   ├── command_audit.py          # Structured, sanitized remote-command audit logging
│   ├── system_actions.py         # /cpu, /ram, /disk, /battery, /uptime, /system
│   ├── security_actions.py       # /sessions, /security, /events, /audit, /lastboot, /health, /version
│   ├── power_actions.py          # /lock, /shutdown, /confirm_shutdown, /restart, /confirm_restart
│   ├── file_actions.py           # /find, /list, /fileinfo, /open (restricted approved roots)
│   ├── network_actions.py        # /ping, /publicip, /network, /wifi (credential-safe)
│   ├── agent_actions.py          # /agent, /restart_agent (decoupled lifecycle controls)
│   ├── remote_actions.py         # v0.4 sensory actions (/status, /location, /screenshot, /processes, /camera)
│   ├── consent_camera.py         # Isolated camera helper with visible on-screen active indicator
│   ├── location.py               # 3-Tier Geolocation Engine & 1h cache manager
│   ├── session_monitor.py        # Win32 WTSRegisterSessionNotification daemon
│   ├── system_info.py            # Battery status, OS, username, and device info
│   ├── network.py                # Public IP detection & multi-provider IP fallback
│   ├── notifications.py          # HTML message builder with event & tier rendering
│   └── telegram.py               # Telegram API client with resilient retry loops
│
├── power_monitor.py              # CLI entry point (startup, shutdown, lock, unlock, session_monitor, command_engine)
├── silent_runner.vbs             # Silent VBScript wrapper for background execution
├── requirements.txt              # Dependencies (requests, python-dotenv, psutil, winrt, PySide6)
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git exclusion rules
│
├── tests/                        # Comprehensive test suite (Unit, Real E2E, Simulated, Safety)
│   ├── test_agent_actions.py
│   ├── test_command_audit.py
│   ├── test_command_auth.py
│   ├── test_command_engine.py
│   ├── test_existing_regression.py
│   ├── test_file_actions.py
│   ├── test_network_actions.py
│   ├── test_power_actions.py
│   ├── test_remote_actions.py
│   ├── test_security_actions.py
│   └── test_system_actions.py
│
├── .env                          # Local credentials (NEVER committed)
├── .location_cache.json          # Local location cache (NEVER committed)
├── .update_state.json            # Polling deduplication state (NEVER committed)
└── error.log                     # Local error logs (NEVER committed)
```

---

## ⚙️ Requirements

* **Operating System:** Windows 10 / 11 (64-bit)
* **Python:** Python 3.13+ (or 3.10+)
* **Dependencies:** `requests`, `python-dotenv`, `psutil`, `PySide6`, `winrt-Windows.Devices.Geolocation`, `winrt-Windows.Foundation`
* **Accounts:** Telegram account and Telegram Bot token via BotFather

---

## 📦 Installation & Setup

1. **Clone repository:**
   ```powershell
   git clone https://github.com/shivdhiksh/sentinel-boot-tracker.git
   cd sentinel-boot-tracker
   py -m pip install -r requirements.txt
   ```

2. **Configure environment:**
   Create `.env` based on `.env.example`:
   ```env
   TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
   TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
   AUTHORIZED_CHAT_ID="YOUR_CHAT_ID"
   ```

3. **Run test suite:**
   ```powershell
   py -m pytest -v
   ```

4. **Start background monitor and command engine:**
   ```powershell
   py power_monitor.py session_monitor
   ```

5. **Configure Remote Camera (Owner Local Opt-In):**
   Remote Camera is **disabled by default** to protect owner privacy. The laptop owner can enable, inspect, or immediately disable it locally at any time:
   ```powershell
   # Enable automatic camera capture for authorized /camera requests:
   py power_monitor.py camera-enable

   # Check current camera opt-in status:
   py power_monitor.py camera-status

   # Immediately disable remote camera capture:
   py power_monitor.py camera-disable
   ```
   * **No Repeated Popup:** Once enabled locally, authorized `/camera` commands capture exactly one photo automatically without requiring an "Allow" click on every request.
   * **Visible Active Indicator:** While the camera hardware is initializing and capturing (~900ms), a prominent on-screen banner (`🔴 WEBCAM ACTIVE`) is displayed on the user's desktop.
   * **Windows OS & Privacy Controls:** Sentinel respects Windows camera permissions and restricts execution strictly to interactive user console sessions (rejecting Session 0 / SYSTEM calls).
   * **Data Cleanup:** Captured images are deleted immediately from disk after upload attempts (on success, transmission failure, camera driver errors, or timeouts).
   * **Local Admin Only:** Remote Camera can only be enabled locally from the laptop terminal. Telegram commands cannot enable the feature remotely.

---

## 🧪 Testing & Safety

Sentinel test suite uses explicit classifications:
* `[REAL E2E]` — Non-destructive live hardware and OS telemetry verification.
* `[UNIT]` — Component, helper, and state machine isolation tests.
* `[SIMULATED]` — Network timeouts, socket failures, and disconnect simulations.
* `[SAFETY]` — Automated interception that hard-blocks any invocation of `shutdown.exe` (`/s` or `/r`).
* `[STATIC/INSPECTION]` — Static source code analysis verifying no credential leaks or unsafe flags.
* `[MANUAL]` — Gated camera and screen capture tests (explicitly require `SENTINEL_RUN_MANUAL_TESTS=1`).

---

## 👨‍💻 Author

**Shiva Dhikshith**  
* GitHub: [@shivdhiksh](https://github.com/shivdhiksh)  
* LinkedIn: [@shivdhiksh](https://www.linkedin.com/in/shivdhiksh)

---

*Licensed for educational and personal use.*
