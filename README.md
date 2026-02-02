# 🏥 Rafeeq: Advanced Health Monitoring System

**Rafeeq** (Arabic for *Companion*) is an intelligent health monitoring dashboard designed for elderly care and patient safety. It combines real-time vital sign tracking with emotional intelligence and automated emergency response.

---

## 🌟 Overview
The system monitors three critical health metrics—**Heart Rate, SpO2, and Temperature**—while calculating an **Emotional State** based on physiological stress indicators. If the system detects a fall or a critical health spike, it automatically initiates an emergency voice call to the caregiver using the Twilio API.

### 🚀 Key Features
* **Live Dashboard:** A modern UI built with `CustomTkinter` for real-time monitoring.
* **🧠 AI Emotion Analysis:** A rule-based engine that classifies patient status from "Stable" to "Critical Distress."
* **📞 Automated Emergency Calls:** Places real-time voice calls with localized **Arabic** messages describing the specific emergency.
* **📊 Smart Logging:** Automatically creates and maintains an Excel database (`Rafeeq_Continuous_Monitor.xlsx`) on the desktop for medical history.
* **🚨 Fall & Help Detection:** Dedicated triggers for physical trauma or manual patient assistance requests.

---

## 🛠️ Installation & Setup

1. **Clone the Repository:**
    ```bash
    git clone [https://github.com/your-username/rafeeq-monitor.git](https://github.com/your-username/rafeeq-monitor.git)
    cd rafeeq-monitor
    ```

2. **Install Dependencies:**
    ```bash
    pip install customtkinter twilio pandas openpyxl python-dotenv
    ```

3. **Configuration:**
    * Create a `.env` file in the root directory.
    * Add your Twilio credentials to the `.env` file to keep them secure:
    ```env
    TWILIO_ACCOUNT_SID=your_sid
    TWILIO_AUTH_TOKEN=your_token
    TWILIO_PHONE_NUMBER=your_twilio_number
    CAREGIVER_PHONE=target_phone_number
    ```

---

## 📊 Technical Thresholds

The system evaluates patient safety based on the following metrics:

| Metric | Warning Level | Critical Level |
| :--- | :--- | :--- |
| **Heart Rate** | 120 BPM | 140 BPM |
| **SpO2 (Oxygen)** | 93% | 90% |
| **Temperature** | 37.5°C | 38.5°C |

---

## 🖼️ System Preview
![System Running](system_running.png)

---

## 🛡️ Safety Note
To protect your Twilio account, ensure that your `.env` file is added to your `.gitignore` before pushing this project to a public repository.

---

## 📄 License
Open-source prototype for educational and healthcare development.
