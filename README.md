# 🛡️ Sentinel Boot Tracker

A lightweight Windows laptop monitoring tool that sends real-time **Telegram notifications** when a laptop starts up or shuts down.

The project is designed to provide a simple personal security and activity-monitoring mechanism for a Windows computer.

## 🚀 Project Overview

**Sentinel Boot Tracker** monitors important Windows power events and sends an alert directly to the user's Telegram account.

The current implementation uses:

* 🐍 Python for the monitoring logic
* 🤖 Telegram Bot API for notifications
* 🪟 Windows Task Scheduler for automation
* 📜 VBScript for silent background execution
* 🔐 `.env` for secure credential configuration

### Current workflow

```text
Windows Laptop
      │
      ├── Startup
      │
      ▼
Windows Task Scheduler
      │
      ▼
silent_runner.vbs
      │
      ▼
power_monitor.py
      │
      ▼
Telegram Bot API
      │
      ▼
📱 Telegram Notification
```

## ✨ Features

### Currently implemented

* ✅ Telegram Bot API integration
* ✅ Startup notification
* ✅ Shutdown notification through the Python command
* ✅ Silent background execution using VBScript
* ✅ Python 3.13 support
* ✅ Automatic `.env` loading
* ✅ Startup network retry mechanism
* ✅ Shutdown retry mechanism
* ✅ Error logging
* ✅ Telegram token sanitization in logs
* ✅ Dynamic project path resolution
* ✅ Windows Task Scheduler startup automation
* ✅ No console window when using the silent runner
* ✅ Sensitive `.env` file excluded from Git

### In development

* 🚧 Automatic Windows shutdown event detection
* 🚧 Restart detection
* 🚧 Sleep/wake detection
* 🚧 Improved event history
* 🚧 Installation/setup automation
* 🚧 Extended system information

## 🏗️ Project Structure

```text
sentinel-boot-tracker/
│
├── .env.example          # Environment variable template
├── .gitignore            # Files excluded from Git
├── power_monitor.py      # Core Telegram notification logic
├── requirements.txt      # Python dependencies
├── silent_runner.vbs     # Silent Windows execution wrapper
│
└── .env                  # Local credentials - NOT committed
```

## ⚙️ Requirements

* Windows 10/11
* Python 3.13+
* Telegram account
* Telegram bot
* Internet connection

## 📦 Installation

Clone the repository:

```bash
git clone https://github.com/shivdhiksh/sentinel-boot-tracker.git
cd sentinel-boot-tracker
```

Install the Python dependencies:

```powershell
py -m pip install -r requirements.txt
```

## 🤖 Telegram Bot Setup

Create a Telegram bot using **BotFather**.

After creating the bot, obtain:

* Telegram Bot Token
* Telegram Chat ID

Create a `.env` file in the project directory:

```env
TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID="YOUR_CHAT_ID"
```

⚠️ **Never commit ****`.env`**** to GitHub.**

The project already includes `.gitignore` rules to keep the credentials private.

## 🧪 Manual Testing

### Test startup notification

```powershell
py power_monitor.py startup
```

### Test shutdown notification

```powershell
py power_monitor.py shutdown
```

A successful execution should produce:

```text
Success: Telegram alert sent successfully.
```

and a Telegram notification should arrive on the configured phone.

## 🔕 Silent Execution

The project includes `silent_runner.vbs` so that Python can run without opening a visible Command Prompt window.

### Startup

```powershell
wscript silent_runner.vbs startup
```

### Shutdown

```powershell
wscript silent_runner.vbs shutdown
```

The silent runner dynamically locates the project directory and launches the configured Python interpreter without displaying a console window.

## 🪟 Windows Startup Automation

The current version uses **Windows Task Scheduler** to automatically execute the startup notification when the configured Windows user logs in.

The workflow is:

```text
Windows Login
     ↓
Task Scheduler
     ↓
silent_runner.vbs startup
     ↓
power_monitor.py
     ↓
Telegram
```

The startup task has been manually tested successfully.

## 🌐 Network Resilience

Windows may finish starting before the Wi-Fi or internet connection is ready.

To handle this, the startup notification includes retry logic.

Current configuration:

```text
Startup:
10 attempts
5-second delay

Shutdown:
3 attempts
1-second delay
```

This gives the notification system an opportunity to recover from temporary network availability problems.

## 🔐 Security

Sensitive credentials are intentionally excluded from the repository.

The following files are ignored:

```text
.env
error.log
__pycache__/
*.pyc
```

The repository contains `.env.example` instead of the real credentials.

The application also sanitizes Telegram bot tokens before writing exception information to logs.

### Never commit:

```text
.env
```

## 🧪 Current Validation

The following components have been tested successfully:

| Component                      | Status |
| ------------------------------ | ------ |
| Telegram Bot API               | ✅ PASS |
| Correct Telegram Chat ID       | ✅ PASS |
| Python startup notification    | ✅ PASS |
| Python shutdown notification   | ✅ PASS |
| Silent startup execution       | ✅ PASS |
| Silent shutdown execution      | ✅ PASS |
| Token sanitization             | ✅ PASS |
| Dynamic path resolution        | ✅ PASS |
| Windows Task Scheduler startup | ✅ PASS |

## 🗺️ Roadmap

### Version 0.1 — Core Monitoring

* [x] Python notification engine
* [x] Telegram integration
* [x] Environment configuration
* [x] Silent execution
* [x] Startup automation
* [x] Security cleanup

### Version 0.2 — Power Event Automation

* [ ] Automatic shutdown detection
* [ ] Restart detection
* [ ] Better Windows event handling
* [ ] Shutdown reliability testing

### Version 0.3 — Monitoring & History

* [ ] Local event database
* [ ] Startup/shutdown history
* [ ] Event timestamps
* [ ] Session duration tracking
* [ ] System information

### Version 1.0 — Complete Sentinel

* [ ] Automatic installer
* [ ] Configuration wizard
* [ ] Background service
* [ ] Dashboard
* [ ] Advanced security monitoring
* [ ] Release packaging

## 📸 Example Notification

Example startup alert:

```text
🚀 ASUS TUF Alert: System Startup
━━━━━━━━━━━━━━━━━━━━━━
💻 Device: ASUS TUF A15
🕒 Time: 2026-08-19 11:30:00 PM
⚡ Status: Event triggered and confirmed
```

## 🎯 Why This Project?

The project demonstrates how a local Windows system can communicate with a cloud-based notification service.

It combines:

* Python development
* REST APIs
* Windows automation
* Task Scheduler
* Environment variables
* Error handling
* Network resilience
* Background process execution
* Basic security practices

## 👨‍💻 Author

**Shiva Dhikshith**

GitHub: [@shivdhiksh](https://github.com/shivdhiksh)

Linkdin: [@shivdhiksh](www.linkedin.com/in/shivdhiksh)


This project is currently provided for educational and personal use.
