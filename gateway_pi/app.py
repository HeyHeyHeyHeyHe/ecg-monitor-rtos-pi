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

# --- SYSTEM STATUS VARIABLE ---
is_running = True

# --- NEW GLOBAL VARIABLE: Cờ báo hiệu cần dịch chuyển con trỏ đọc xuống đáy file ---
should_seek_to_end = False

try:
    open(FLAG_FILE_NAME, 'w').close()
except Exception:
    pass

@app.route('/')
def index():
    return render_template('index.html')

# --- HANDLE START/STOP TOGGLE ---
@socketio.on('toggle_system')
def handle_toggle(data):
    global is_running, should_seek_to_end
    is_running = data['status']
    
    if is_running:
        try:
            # 1. Bật cờ báo hiệu cho luồng ngầm biết cần nhảy xuống dòng cuối cùng ngay
            should_seek_to_end = True
            
            # 2. Tạo file flag để uart_reader.py tiếp tục ghi dữ liệu vào file cũ
            open(FLAG_FILE_NAME, 'w').close()
            print("[SYSTEM] System RESUMED instantly. Appending to existing log.")
        except Exception as e:
            print(f"[ERROR] Failed to switch to START state: {e}")
    else:
        try:
            if os.path.exists(FLAG_FILE_NAME):
                os.remove(FLAG_FILE_NAME)
            print("[SYSTEM] Session PAUSED. Current data remains completely intact.")
        except Exception as e:
            print(f"[ERROR] Failed to switch to STOP state: {e}")

@app.route('/export-report', methods=['POST'])
def export_report_api():
    try:
        # Gọi script sinh file ảnh ngầm
        result = subprocess.run(['python3', 'analyze_day3_4.py'], capture_output=True, text=True, check=True)
        print(f"[SYSTEM] Script output: {result.stdout}")
        
        # --- SỬA DÒNG RETURN CŨ THÀNH DÒNG NÀY ---
        # Gửi file ảnh trực tiếp về trình duyệt để tải xuống
        return send_file('ecg_advanced_report.png', as_attachment=True)
        
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Lỗi khi chạy script phân tích: {e.stderr}")
        return "Lỗi thực thi hệ thống ngầm", 500
    except Exception as e:
        return str(e), 500
def watch_csv_and_emit():
    global should_seek_to_end
    print("[SYSTEM] Background thread is checking CSV file...")
    while not os.path.exists(CSV_FILE_NAME):
        eventlet.sleep(0.5)

    with open(CSV_FILE_NAME, mode='r') as f:
        # Lần đầu tiên chạy Server: Nhảy xuống đáy file để lấy dữ liệu realtime mới nhất
        f.seek(0, os.SEEK_END)

        while True:
            # --- NEW LOGIC: Nếu người dùng vừa bấm START lại, lập tức nhảy xuống đáy file hiện tại ---
            if should_seek_to_end:
                f.seek(0, os.SEEK_END)
                should_seek_to_end = False # Xoá cờ sau khi đã dịch con trỏ xong
                print("[SYSTEM] Reader synchronized! Jumped to the end of file for the new session.")

            if not is_running:
                eventlet.sleep(0.1)
                continue

            # -----------------------------------------------------------------
            # --- OPTIMIZED LOGIC: BURST READ TO ELIMINATE REALTIME LATENCY ---
            # -----------------------------------------------------------------
            has_data = False
            
            # Đọc liên tục (vòng lặp cạn dòng) tất cả các dòng UART vừa mới ghi vào file CSV
            while True:
                line = f.readline()
                if not line:
                    break # Không còn dòng mới nào ở thời điểm này -> Thoát ra để nhường luồng
                
                has_data = True
                parts = line.strip().split(',')
                if len(parts) >= 6:
                    try:
                        data_packet = {
                            "bpm": parts[4],       
                            "signal": float(parts[3]), 
                            "status": parts[6]     
                        }
                        # Đẩy dữ liệu lên giao diện Web ngay lập tức
                        socketio.emit('ecg_data', data_packet)
                    except ValueError:
                        continue

            # Nếu trong chu kỳ quét này file CSV trống (UART chưa ghi thêm dòng nào mới)
            if not has_data:
                # Ngủ cực ngắn (1ms) để giải phóng CPU cho Pi mà vẫn bám sát nút file CSV
                eventlet.sleep(0.04)
            # -----------------------------------------------------------------

def clean_up_csv():
    if os.path.exists(CSV_FILE_NAME):
        os.remove(CSV_FILE_NAME)
    if os.path.exists(FLAG_FILE_NAME):
        os.remove(FLAG_FILE_NAME)

if __name__ == '__main__':
    atexit.register(clean_up_csv)
    eventlet.spawn(watch_csv_and_emit)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)