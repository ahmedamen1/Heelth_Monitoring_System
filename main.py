import customtkinter as ctk
import threading
from twilio.rest import Client
import time
from datetime import datetime
from collections import deque
import random
import pandas as pd
from pathlib import Path
import os

# Load variables from .env file
load_dotenv()

# --- CONFIGURATION ---
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
CAREGIVER_ID = os.getenv("CAREGIVER_PHONE")


# --- THRESHOLDS ---
HEART_RATE_CRITICAL = 140
HEART_RATE_WARNING = 120
SPO2_CRITICAL = 90
SPO2_WARNING = 93
TEMP_CRITICAL_HIGH = 38.5
TEMP_CRITICAL_LOW = 35.5

# Auto-call cooldown (prevent spam)
LAST_AUTO_CALL = None
AUTO_CALL_COOLDOWN = 30  # seconds between auto-calls


# --- EMOTION ANALYSIS ENGINE ---
class EmotionAnalyzer:
    """Simple rule-based emotion detection from vital signs"""

    @staticmethod
    def analyze(heart_rate, spo2, temp, fall_detected, help_pressed):
        score = 0
        factors = []

        # Heart Rate Analysis
        if heart_rate > 130:
            score += 30
            factors.append("elevated_hr")
        elif heart_rate > 110:
            score += 15
            factors.append("raised_hr")

        # SpO2 Analysis
        if spo2 < 92:
            score += 25
            factors.append("low_oxygen")
        elif spo2 < 95:
            score += 10
            factors.append("reduced_oxygen")

        # Temperature Analysis
        if temp > 38 or temp < 36:
            score += 15
            factors.append("temp_abnormal")

        # Critical Events
        if fall_detected:
            score += 40
            factors.append("fall_trauma")

        if help_pressed:
            score += 35
            factors.append("distress_signal")

        # Emotion Classification
        if score >= 60:
            emotion = "CRITICAL DISTRESS"
            color = "#D50000"
        elif score >= 40:
            emotion = "HIGH ANXIETY"
            color = "#FF6D00"
        elif score >= 25:
            emotion = "MODERATE STRESS"
            color = "#FFA000"
        elif score >= 10:
            emotion = "MILD DISCOMFORT"
            color = "#FBC02D"
        else:
            emotion = "STABLE"
            color = "#00C853"

        return {
            "emotion": emotion,
            "score": score,
            "color": color,
            "factors": factors
        }


# --- DATA MANAGER (Time Series + Excel Export) ---
class VitalSignsMonitor:
    def __init__(self):
        # Emergency Events
        self.fall_events = []
        self.help_requests = []
        self.emergency_calls = []

        # Excel Export Path - Try multiple locations
        possible_paths = [
            Path.home() / "Desktop",
            Path.home() / "OneDrive" / "Desktop",
            Path.home() / "OneDrive" / "سطح المكتب",  # Arabic Desktop
            Path.home() / "سطح المكتب",  # Arabic Desktop direct
            Path.home() / "Documents",
            Path.home()  # Home directory as fallback
        ]

        # Find first existing directory
        save_location = None
        for path in possible_paths:
            if path.exists():
                save_location = path
                break

        if save_location is None:
            save_location = Path.home()
            save_location.mkdir(exist_ok=True)

        self.excel_file = save_location / "Rafeeq_Continuous_Monitor.xlsx"
        print(f"📂 Excel file will be saved to: {self.excel_file}")

        # Initialize Excel file with headers if doesn't exist
        self.init_excel_file()

    def init_excel_file(self):
        """Create Excel file with all sheets if it doesn't exist"""
        if not self.excel_file.exists():
            with pd.ExcelWriter(self.excel_file, engine='openpyxl') as writer:
                # Vital Signs Sheet
                pd.DataFrame(columns=[
                    'Timestamp', 'Heart_Rate_BPM', 'SpO2_Percent',
                    'Temperature_Celsius', 'Emotional_State', 'Emotion_Score'
                ]).to_excel(writer, sheet_name='Vital_Signs', index=False)

                # Emergency Calls Sheet
                pd.DataFrame(columns=[
                    'Timestamp', 'Alert_Type', 'Heart_Rate', 'SpO2',
                    'Temperature', 'Emotion_State', 'Auto_Triggered'
                ]).to_excel(writer, sheet_name='Emergency_Calls', index=False)

                # Fall Events Sheet
                pd.DataFrame(columns=['Fall_Timestamp']).to_excel(
                    writer, sheet_name='Fall_Events', index=False)

                # Help Requests Sheet
                pd.DataFrame(columns=['Help_Request_Timestamp']).to_excel(
                    writer, sheet_name='Help_Requests', index=False)

            print(f"✅ Excel file created at: {self.excel_file}")

    def append_vital_reading(self, hr, spo2, temp, emotion, score):
        """Append a single vital sign reading to Excel"""
        try:
            new_row = pd.DataFrame([{
                'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Heart_Rate_BPM': hr,
                'SpO2_Percent': spo2,
                'Temperature_Celsius': temp,
                'Emotional_State': emotion,
                'Emotion_Score': score
            }])

            # Read existing data
            existing_df = pd.read_excel(self.excel_file, sheet_name='Vital_Signs')

            # Append new row
            updated_df = pd.concat([existing_df, new_row], ignore_index=True)

            # Write back (preserving other sheets)
            with pd.ExcelWriter(self.excel_file, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                updated_df.to_excel(writer, sheet_name='Vital_Signs', index=False)

        except Exception as e:
            print(f"❌ Error appending vital reading: {e}")

    def append_emergency_call(self, alert_type, hr, spo2, temp, emotion, auto_triggered=False):
        """Append emergency call to Excel"""
        try:
            new_row = pd.DataFrame([{
                'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Alert_Type': alert_type,
                'Heart_Rate': hr,
                'SpO2': spo2,
                'Temperature': temp,
                'Emotion_State': emotion,
                'Auto_Triggered': 'YES' if auto_triggered else 'NO'
            }])

            existing_df = pd.read_excel(self.excel_file, sheet_name='Emergency_Calls')
            updated_df = pd.concat([existing_df, new_row], ignore_index=True)

            with pd.ExcelWriter(self.excel_file, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                updated_df.to_excel(writer, sheet_name='Emergency_Calls', index=False)

        except Exception as e:
            print(f"❌ Error appending emergency call: {e}")

    def append_fall_event(self):
        """Append fall event to Excel"""
        try:
            new_row = pd.DataFrame([{
                'Fall_Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])

            existing_df = pd.read_excel(self.excel_file, sheet_name='Fall_Events')
            updated_df = pd.concat([existing_df, new_row], ignore_index=True)

            with pd.ExcelWriter(self.excel_file, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                updated_df.to_excel(writer, sheet_name='Fall_Events', index=False)

        except Exception as e:
            print(f"❌ Error appending fall event: {e}")

    def append_help_request(self):
        """Append help request to Excel"""
        try:
            new_row = pd.DataFrame([{
                'Help_Request_Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])

            existing_df = pd.read_excel(self.excel_file, sheet_name='Help_Requests')
            updated_df = pd.concat([existing_df, new_row], ignore_index=True)

            with pd.ExcelWriter(self.excel_file, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                updated_df.to_excel(writer, sheet_name='Help_Requests', index=False)

        except Exception as e:
            print(f"❌ Error appending help request: {e}")


# --- EMERGENCY CALL HANDLER ---
def trigger_emergency_call(alert_type, sensor_data, status_label, call_counter_label, monitor, auto_triggered=False):
    global LAST_AUTO_CALL

    client = Client(ACCOUNT_SID, AUTH_TOKEN)

    # Get current vitals
    hr = sensor_data.get('hr', 0)
    spo2 = sensor_data.get('spo2', 0)
    temp = sensor_data.get('temp', 0)
    fall = sensor_data.get('fall', False)
    help_btn = sensor_data.get('help', False)

    # Emotion Analysis
    emotion_state = EmotionAnalyzer.analyze(hr, spo2, temp, fall, help_btn)

    # Log to Excel
    monitor.append_emergency_call(alert_type, hr, spo2, temp, emotion_state['emotion'], auto_triggered)

    # Build Arabic Message
    auto_prefix = "تنبيه تلقائي. " if auto_triggered else ""

    if alert_type == "HELP":
        reason = f"{auto_prefix}المريض يطلب المساعدة. الحالة النفسية: {emotion_state['emotion']}"
        monitor.append_help_request()
    elif alert_type == "HEART":
        reason = f"{auto_prefix}دقات القلب {hr}. أعلى من الحد الطبيعي"
    elif alert_type == "FALL":
        reason = f"{auto_prefix}كشف السقوط. تحتاج إلى مساعدة فورية"
        monitor.append_fall_event()
    elif alert_type == "SPO2":
        reason = f"{auto_prefix}مستوى الأكسجين منخفض. {spo2} بالمئة"
    elif alert_type == "TEMP":
        reason = f"{auto_prefix}درجة الحرارة غير طبيعية. {temp} درجة"
    else:
        reason = f"{auto_prefix}حالة طوارئ عامة"

    # Update GUI
    auto_text = " [AUTO-TRIGGERED]" if auto_triggered else ""
    status_label.configure(
        text=f"🚨 {alert_type} ALERT{auto_text} | Emotion: {emotion_state['emotion']}",
        text_color=emotion_state['color']
    )

    # Make Voice Call
    try:
        twiml_msg = f"""
        <Response>
            <Say voice="Polly.Zeina" language="ar-SA">
                نظام رفيق للمراقبة الصحية.
                تنبيه عاجل.
                {reason}.
                معدل النبض {hr}.
                الأكسجين {spo2} بالمئة.
                درجة الحرارة {temp}.
                يرجى التحقق من حالة المريض فوراً.
            </Say>
        </Response>
        """
        call = client.calls.create(
            to=CAREGIVER_ID,
            from_=TWILIO_NUMBER,
            twiml=twiml_msg
        )
        print(f"📞 {'[AUTO] ' if auto_triggered else ''}Call Initiated: {call.sid}")

        # Increment Call Counter
        current = int(call_counter_label.cget("text").split(":")[1].strip())
        call_counter_label.configure(text=f"Total Calls: {current + 1}")

        # Update last auto-call time
        if auto_triggered:
            LAST_AUTO_CALL = time.time()

    except Exception as e:
        print(f"❌ Call Failed: {e}")
        status_label.configure(text=f"⚠️ Call Error: {str(e)}", text_color="#FF5252")

    time.sleep(2)
    status_label.configure(text="✅ Alert Processed. Monitoring...", text_color="#00E676")


# --- SENSOR SIMULATOR WITH AUTO-ALERT ---
def simulate_sensor_readings(monitor, hr_label, spo2_label, temp_label, emotion_label,
                             trend_label, status_label, call_counter_label, unstable_case_label):
    """Continuous background simulation with random spikes and auto-alerts"""
    global LAST_AUTO_CALL

    # Base values (normal range)
    base_hr = 75
    base_spo2 = 97
    base_temp = 36.8

    reading_count = 0

    while True:
        reading_count += 1

        # Normal variation
        hr = base_hr + random.randint(-5, 5)
        spo2 = base_spo2 + random.randint(-1, 1)
        temp = round(base_temp + random.uniform(-0.2, 0.2), 1)

        # RANDOM SPIKE GENERATION (Every 15-30 readings)
        should_spike = random.randint(1, 25) == 1  # ~4% chance each reading

        if should_spike:
            spike_type = random.choice(['HEART', 'SPO2', 'TEMP'])

            if spike_type == 'HEART':
                hr = random.randint(145, 165)  # Critical heart rate
            elif spike_type == 'SPO2':
                spo2 = random.randint(85, 91)  # Critical low oxygen
            elif spike_type == 'TEMP':
                temp = round(random.uniform(38.6, 39.5), 1)  # High fever

        # Emotion Analysis
        emotion = EmotionAnalyzer.analyze(hr, spo2, temp, False, False)

        # Save to Excel (every reading)
        monitor.append_vital_reading(hr, spo2, temp, emotion['emotion'], emotion['score'])

        # Update GUI
        hr_label.configure(text=f"❤️ Heart Rate: {hr} BPM")
        spo2_label.configure(text=f"🫁 SpO2: {spo2}%")
        temp_label.configure(text=f"🌡️ Temperature: {temp}°C")

        emotion_label.configure(
            text=f"🧠 Emotional State: {emotion['emotion']}",
            text_color=emotion['color']
        )

        # Update trend placeholder
        trend_label.configure(text=f"📊 Reading #{reading_count}")

        # DISPLAY UNSTABLE CASES
        unstable_factors = []
        if hr > HEART_RATE_WARNING:
            unstable_factors.append(f"High HR ({hr})")
        if spo2 < SPO2_WARNING:
            unstable_factors.append(f"Low O2 ({spo2}%)")
        if temp > TEMP_CRITICAL_HIGH or temp < TEMP_CRITICAL_LOW:
            unstable_factors.append(f"Abnormal Temp ({temp}°C)")

        if emotion['emotion'] != "STABLE":
            case_text = f"⚠️ UNSTABLE: {emotion['emotion']} | Factors: {', '.join(unstable_factors) if unstable_factors else 'Emotional stress detected'}"
            unstable_case_label.configure(text=case_text, text_color=emotion['color'])
        else:
            unstable_case_label.configure(text="✅ Patient Status: STABLE", text_color="#00C853")

        # AUTO-TRIGGER EMERGENCY CALL IF CRITICAL
        if should_spike or emotion['score'] >= 25:
            # Check cooldown
            current_time = time.time()
            if LAST_AUTO_CALL is None or (current_time - LAST_AUTO_CALL) >= AUTO_CALL_COOLDOWN:

                # Determine alert type
                if hr > HEART_RATE_CRITICAL:
                    alert_type = "HEART"
                elif spo2 < SPO2_CRITICAL:
                    alert_type = "SPO2"
                elif temp > TEMP_CRITICAL_HIGH:
                    alert_type = "TEMP"
                else:
                    alert_type = "GENERAL"

                sensor_data = {
                    'hr': hr,
                    'spo2': spo2,
                    'temp': temp,
                    'fall': False,
                    'help': False
                }

                print(f"🔔 AUTO-ALERT TRIGGERED: {alert_type} | HR={hr}, SpO2={spo2}, Temp={temp}")

                # Trigger call in separate thread
                threading.Thread(target=trigger_emergency_call,
                                 args=(alert_type, sensor_data, status_label,
                                       call_counter_label, monitor, True),
                                 daemon=True).start()

        time.sleep(3)  # Update every 3 seconds


# --- MAIN GUI ---
class RafeeqAdvancedSystem(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Rafeeq Advanced Health Monitoring System")
        self.geometry("950x850")
        ctk.set_appearance_mode("Dark")

        # Data Monitor
        self.monitor = VitalSignsMonitor()

        # Header
        header = ctk.CTkLabel(self, text="🏥 RAFEEQ HEALTH MONITOR",
                              font=("Arial", 32, "bold"), text_color="#00E676")
        header.pack(pady=15)

        # Excel File Location
        excel_path_label = ctk.CTkLabel(self,
                                        text=f"📁 Excel File: {self.monitor.excel_file.name}",
                                        font=("Arial", 11), text_color="#64B5F6")
        excel_path_label.pack()

        # Status Bar
        self.status_label = ctk.CTkLabel(self, text="✅ SYSTEM ACTIVE - MONITORING PATIENT",
                                         font=("Courier", 16), text_color="#00E676")
        self.status_label.pack(pady=10)

        # Call Counter
        self.call_counter = ctk.CTkLabel(self, text="Total Calls: 0",
                                         font=("Arial", 14, "bold"))
        self.call_counter.pack()

        # UNSTABLE CASE INDICATOR
        self.unstable_case_label = ctk.CTkLabel(self, text="✅ Patient Status: STABLE",
                                                font=("Courier", 14, "bold"),
                                                text_color="#00C853")
        self.unstable_case_label.pack(pady=10)

        # --- LIVE VITALS PANEL ---
        vitals_frame = ctk.CTkFrame(self)
        vitals_frame.pack(pady=15, padx=20, fill="x")

        ctk.CTkLabel(vitals_frame, text="📡 LIVE VITALS (Auto-Updating)",
                     font=("Arial", 18, "bold")).pack(pady=5)

        self.hr_label = ctk.CTkLabel(vitals_frame, text="❤️ Heart Rate: -- BPM",
                                     font=("Courier", 16))
        self.hr_label.pack(pady=3)

        self.spo2_label = ctk.CTkLabel(vitals_frame, text="🫁 SpO2: -- %",
                                       font=("Courier", 16))
        self.spo2_label.pack(pady=3)

        self.temp_label = ctk.CTkLabel(vitals_frame, text="🌡️ Temperature: -- °C",
                                       font=("Courier", 16))
        self.temp_label.pack(pady=3)

        self.emotion_label = ctk.CTkLabel(vitals_frame, text="🧠 Emotional State: STABLE",
                                          font=("Courier", 15, "bold"), text_color="#00C853")
        self.emotion_label.pack(pady=5)

        self.trend_label = ctk.CTkLabel(vitals_frame, text="📊 Reading #0",
                                        font=("Courier", 14))
        self.trend_label.pack(pady=3)

        # Auto-Alert Info
        info_label = ctk.CTkLabel(vitals_frame,
                                  text="🔔 System will AUTO-CALL on critical readings (30s cooldown)",
                                  font=("Arial", 11), text_color="#FFA726")
        info_label.pack(pady=5)

        # --- MANUAL EMERGENCY SIMULATION BUTTONS ---
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=15, padx=20, fill="both", expand=True)

        ctk.CTkLabel(btn_frame, text="⚠️ MANUAL EMERGENCY SIMULATIONS",
                     font=("Arial", 18, "bold")).pack(pady=10)

        # Critical Heart Rate
        ctk.CTkButton(btn_frame, text="💔 CRITICAL Heart Rate (155 BPM)",
                      fg_color="#D50000", height=50, font=("Arial", 14, "bold"),
                      command=lambda: self.trigger_alert("HEART", 155, 96, 37.0)).pack(pady=6, fill="x", padx=40)

        # Low Oxygen
        ctk.CTkButton(btn_frame, text="🫁 LOW Oxygen Saturation (88%)",
                      fg_color="#6A1B9A", height=50, font=("Arial", 14, "bold"),
                      command=lambda: self.trigger_alert("SPO2", 110, 88, 36.9)).pack(pady=6, fill="x", padx=40)

        # Fall Detection
        ctk.CTkButton(btn_frame, text="⤵️ FALL DETECTED",
                      fg_color="#D81B60", height=50, font=("Arial", 14, "bold"),
                      command=lambda: self.trigger_alert("FALL", 120, 95, 37.1, fall=True)).pack(pady=6, fill="x",
                                                                                                 padx=40)

        # Patient Help Request
        ctk.CTkButton(btn_frame, text="✋ PATIENT HELP REQUEST",
                      fg_color="#EF6C00", height=50, font=("Arial", 14, "bold"),
                      command=lambda: self.trigger_alert("HELP", 105, 94, 37.3, help=True)).pack(pady=6, fill="x",
                                                                                                 padx=40)

        # High Temperature
        ctk.CTkButton(btn_frame, text="🌡️ HIGH Temperature (39.2°C)",
                      fg_color="#BF360C", height=50, font=("Arial", 14, "bold"),
                      command=lambda: self.trigger_alert("TEMP", 98, 96, 39.2)).pack(pady=6, fill="x", padx=40)

        # Reset
        ctk.CTkButton(btn_frame, text="♻️ RESET CALL COUNTER",
                      fg_color="#00C853", height=40,
                      command=self.reset_counter).pack(pady=15)

        # Start background sensor simulation with auto-alerts
        threading.Thread(target=simulate_sensor_readings,
                         args=(self.monitor, self.hr_label, self.spo2_label,
                               self.temp_label, self.emotion_label, self.trend_label,
                               self.status_label, self.call_counter, self.unstable_case_label),
                         daemon=True).start()

    def trigger_alert(self, alert_type, hr, spo2, temp, fall=False, help=False):
        sensor_data = {
            'hr': hr,
            'spo2': spo2,
            'temp': temp,
            'fall': fall,
            'help': help
        }

        # Trigger emergency call (manual)
        threading.Thread(target=trigger_emergency_call,
                         args=(alert_type, sensor_data, self.status_label,
                               self.call_counter, self.monitor, False),
                         daemon=True).start()

    def reset_counter(self):
        self.call_counter.configure(text="Total Calls: 0")
        self.status_label.configure(text="✅ SYSTEM ACTIVE - MONITORING PATIENT",
                                    text_color="#00E676")


# --- RUN APPLICATION ---
if __name__ == "__main__":
    print("🚀 Starting Rafeeq Health Monitoring System...")
    app = RafeeqAdvancedSystem()
    app.mainloop()