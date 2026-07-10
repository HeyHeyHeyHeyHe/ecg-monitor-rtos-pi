import subprocess
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, send_file
from flask_socketio import SocketIO
import os
import atexit

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')
CSV_FILE_NAME = "/home/pi/ecg_data_log.csv"
FLAG_FILE_NAME = "/home/pi/sys_active.flag"

# --- SYSTEM STATUS VARIABLES ---
is_running = True
should_seek_to_end = False

# Initialize the system flag file on startup
try: open(FLAG_FILE_NAME, 'w').close()
except Exception: pass

@app.route('/')
def index():
    return render_template('index.html')

# --- HANDLE START/STOP TOGGLE ---
@socketio.on('toggle_system')
def handle_toggle(data):
    global is_running, should_seek_to_end
    is_running = data['status']
    
    if is_running:
        should_seek_to_end = True
        try: open(FLAG_FILE_NAME, 'w').close()
        except Exception: pass
        print("[SYSTEM] System RESUMED instantly.")
    else:
        try:
            if os.path.exists(FLAG_FILE_NAME): os.remove(FLAG_FILE_NAME)
        except Exception: pass
        print("[SYSTEM] Session PAUSED.")

# --- EXPORT REPORT API ENDPOINT ---
@app.route('/export-report', methods=['POST'])
def export_report_api():
    try:
        # Invoke the backend analytical reporting script synchronously
        result = subprocess.run(['python3', 'analyze_day3_4.py'], capture_output=True, text=True, check=True)
        print(f"[SYSTEM] Script output: {result.stdout}")
        
        # Stream the generated report image directly back to the browser for download
        return send_file('ecg_advanced_report.png', as_attachment=True)
        
    except Exception as e:
        print(f"[Export Error] {e}")
        return "Error generating report", 500

# --- BACKGROUND CSV MONITORING & REAL-TIME EMISSION ---
def watch_csv_and_emit():
    global should_seek_to_end
    print("[SYSTEM] Background thread is checking CSV file...")
    
    # Wait until the CSV file is established
    while not os.path.exists(CSV_FILE_NAME):
        eventlet.sleep(0.5)

    with open(CSV_FILE_NAME, mode='r') as f:
        while True:
            #  Check if whether the Start or Stop button is pressed
            if should_seek_to_end:
                f.seek(0, os.SEEK_END)
                should_seek_to_end = False
                print("[SYSTEM] Jumped to the end of file for the new session.")

            # Standby state when the acquisition session is paused
            if not is_running:
                eventlet.sleep(0.1)
                continue

            line = f.readline()
            # If no new line is written yet, yield execution briefly to prevent CPU spinning
            if not line:
                eventlet.sleep(0.04)
                continue

            parts = line.strip().split(',')
            if len(parts) >= 7:
                try:
                    packet = {
                        "bpm": parts[4],
                        "signal": float(parts[3]),
                        "status": parts[6]
                    }
                    # Broadcast data packet to all connected web clients via WebSockets
                    socketio.emit('ecg_data', packet)
                except:
                    pass

# --- SYSTEM SHUTDOWN CLEANUP ---
def clean_up_csv():
    # Delete temporary session flags and raw telemetry logs upon server exit
    for file_path in [CSV_FILE_NAME, FLAG_FILE_NAME]:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except Exception: pass

if __name__ == '__main__':
    # Register the exit handler and spawn the cooperative background worker thread
    atexit.register(clean_up_csv)
    eventlet.spawn(watch_csv_and_emit)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)