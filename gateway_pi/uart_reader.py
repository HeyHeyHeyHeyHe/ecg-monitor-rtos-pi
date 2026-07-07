import serial
import csv
import time
import os

SERIAL_PORT = '/dev/ttyS0' 
BAUD_RATE = 115200
CSV_FILE_NAME = "/home/pi/ecg_data_log.csv"

FLAG_FILE_NAME = "/home/pi/sys_active.flag"

STATUS_MAP = {
    "0": "NORMAL",
    "1": "BRADYCARDIA",
    "2": "TACHYCARDIA",
    "3": "LEADS_OFF"
}

if not os.path.exists(CSV_FILE_NAME):
    with open(CSV_FILE_NAME, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Pi_Local_Time", "ESP32_Timestamp_ms", "Raw_Value", "Filtered_Value", "BPM", "Status_Code", "Status_String"])

try:
    ser = serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUD_RATE,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1
    )
except Exception as e:
    exit()

try:
    while True:
        if ser.in_waiting > 0:
            try:
                raw_line = ser.readline()
                decoded_line = raw_line.decode('utf-8', errors='ignore').strip()
                
                if not decoded_line:
                    continue
                if not os.path.exists(FLAG_FILE_NAME):
                    continue

                data_parts = decoded_line.split(',')
                
                if len(data_parts) == 5:
                    esp32_time = data_parts[0]
                    raw_val = data_parts[1]
                    filtered_val = data_parts[2]
                    bpm = data_parts[3]
                    status_code = data_parts[4]
                    
                    status_str = STATUS_MAP.get(status_code, "UNKNOWN")
                    pi_current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                    
                    print(f"[{pi_current_time}] ESP32-T: {esp32_time}ms | Raw: {raw_val} | Filtered: {filtered_val} | BPM: {bpm} | Status: {status_str}")
                    
                    with open(CSV_FILE_NAME, mode='a', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow([pi_current_time, esp32_time, raw_val, filtered_val, bpm, status_code, status_str])
                        
            except UnicodeDecodeError:
                pass
            except Exception as e:
                pass
                
        time.sleep(0.001)

except KeyboardInterrupt:
    pass
finally:
    ser.close()
