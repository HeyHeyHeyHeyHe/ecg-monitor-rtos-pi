import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

CSV_FILE_PATH = "/home/pi/ecg_data_log.csv"
OUTPUT_IMAGE_PATH = "ecg_advanced_report.png"

def load_raw_data(file_path):
    if not os.path.exists(file_path):
        print(f"[ERROR] Không tìm thấy file tại {file_path}.")
        return None
    
    # Đọc file 7 cột theo đúng cấu trúc thực tế của bạn
    df = pd.read_csv(file_path)
    df['Status_String'] = df['Status_String'].astype(str).str.strip()
    df['BPM'] = pd.to_numeric(df['BPM'], errors='coerce')
    return df

def generate_visual_dashboard(df):
    total_rows = len(df)
    if total_rows == 0:
        print("[WARNING] File CSV không có dữ liệu.")
        return

    # --- 1. THỐNG KÊ TOÁN HỌC THỰC TẾ ---
    SAMPLE_PERIOD_SEC = 0.01  # Tần suất lấy mẫu 10ms/dòng
    total_duration_sec = total_rows * SAMPLE_PERIOD_SEC
    
    # Lọc tập dữ liệu sạch để tính toán nhịp tim và HRV (Bỏ Leads Off và BPM lỗi)
    signal_df = df[(df['BPM'] >= 40) & (df['BPM'] <= 200) & (~df['Status_String'].str.contains('LEADS_OFF|LEAD_OFF', case=False, na=False))]
    leads_off_count = len(df[df['Status_String'].str.contains('LEADS_OFF|LEAD_OFF', case=False, na=False)])
    leads_off_duration_sec = leads_off_count * SAMPLE_PERIOD_SEC

    avg_bpm = signal_df['BPM'].mean() if len(signal_df) > 0 else 0.0
    max_bpm = signal_df['BPM'].max() if len(signal_df) > 0 else 0.0
    min_bpm = signal_df['BPM'].min() if len(signal_df) > 0 else 0.0

    sdnn_val = 0.0
    rmssd_val = 0.0
    has_hrv = False

    if len(signal_df) >= 2:
        # Chuyển đổi từ BPM sang khoảng cách nhịp RR (miligiây)
        rr_intervals = 60000.0 / signal_df['BPM'].values
        
        # 1. Tính SDNN (Độ lệch chuẩn của chuỗi RR)
        sdnn_val = np.std(rr_intervals, ddof=1)
        
        # 2. Tính RMSSD (Căn bình phương trung bình sai biệt các nhịp liên tiếp)
        rr_diff = np.diff(rr_intervals) # Lấy RR_(n+1) - RR_n
        rmssd_val = np.sqrt(np.mean(rr_diff ** 2))
        has_hrv = True

    # --- 2. THIẾT KẾ GIAO DIỆN HIỆN ĐẠI (Grid 2x2) ---
    plt.rcParams['font.family'] = 'sans-serif'
    fig, axs = plt.subplots(2, 2, figsize=(16, 10))
    fig.patch.set_facecolor('#f8fafc') # Đổi nền Dashboard sang màu xám trắng dịu mắt

    # Ô 1 (Top-Left): Biểu đồ tròn trạng thái lâm sàng
    ax1 = axs[0, 0]
    ax1.set_facecolor('#f8fafc')
    status_counts = df['Status_String'].value_counts()
    
    # Phối màu hiện đại (Flat UI Colors)
    color_palette = ['#ff7675', '#fdcb6e', '#00cec9', '#6c5ce7']
    wedges, texts, autotexts = ax1.pie(
        status_counts.values, labels=status_counts.index, autopct='%1.1f%%', 
        startangle=135, colors=color_palette[:len(status_counts)],
        wedgeprops={'edgecolor': '#f8fafc', 'linewidth': 2, 'antialiased': True}
    )
    plt.setp(autotexts, size=10, weight="bold", color="white")
    ax1.set_title('TỶ LỆ PHÂN PHỐI TRẠNG THÁI LÂM SÀNG', fontsize=12, fontweight='bold', color='#2d3748', pad=15)

    # Ô 2 (Top-Right): Đồ thị Poincaré Chuẩn Y Tế (Chỉ nhận RR hợp lệ)
    ax2 = axs[0, 1]
    ax2.set_facecolor('white')
    
    if has_hrv:
        rr_intervals = 60000.0 / signal_df['BPM'].values
        x_rr = rr_intervals[:-1]
        y_rr = rr_intervals[1:]
        
        ax2.scatter(x_rr, y_rr, color='#6c5ce7', alpha=0.6, edgecolors='none', s=25, label='Cặp nhịp $RR_n / RR_{n+1}$')
        min_val, max_val = min(rr_intervals) - 30, max(rr_intervals) + 30
        ax2.set_xlim(min_val, max_val)
        ax2.set_ylim(min_val, max_val)
    else:
        ax2.text(0.5, 0.5, 'MẤT TÍN HIỆU MẠCH\n(Chờ kết nối ESP32...)', 
                 horizontalalignment='center', verticalalignment='center', 
                 transform=ax2.transAxes, fontsize=12, color='#e74c3c', weight='bold')
        min_val, max_val = 400, 1200
        ax2.set_xlim(min_val, max_val)
        ax2.set_ylim(min_val, max_val)

    ax2.plot([min_val, max_val], [min_val, max_val], color='#e17055', linestyle='--', linewidth=1.5, label='Identity Line ($RR_n = RR_{n+1}$)')
    ax2.set_title('ĐỒ THỊ POINCARÉ BIẾN THIÊN NHỊP TIM (HRV)', fontsize=12, fontweight='bold', color='#2d3748', pad=15)
    ax2.set_xlabel('$RR_n$ (Khoảng cách nhịp hiện tại - ms)', fontsize=10, color='#4a5568')
    ax2.set_ylabel('$RR_{n+1}$ (Khoảng cách nhịp kế tiếp - ms)', fontsize=10, color='#4a5568')
    ax2.grid(True, linestyle=':', alpha=0.6, color='#cbd5e1')
    ax2.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='#e2e8f0')

    # Ô 3 (Bottom-Left): Đồ thị đường thời gian (Timeline) dạng bậc thang bước nhảy - ĐÃ CHỈNH SỬA DOWN-SAMPLING ĐỂ KHỚP TỶ LỆ
    ax3 = axs[1, 0]
    ax3.set_facecolor('white')
    
    status_mapping = {'NORMAL': 1, 'TACHYCARDIA': 2, 'BRADYCARDIA': 3, 'LEADS_OFF': 0}
    
    # Thuật toán lấy mẫu thưa (Cứ 10 dòng lốc ~ 0.1s gom thành 1 điểm trạng thái phổ biến nhất)
    STEP_SIZE = 10  
    downsampled_status = []
    downsampled_time = []
    
    for i in range(0, total_rows, STEP_SIZE):
        block = df['Status_String'].iloc[i : i + STEP_SIZE]
        if not block.empty:
            most_frequent = block.value_counts().idxmax()
            downsampled_status.append(status_mapping.get(most_frequent, 0))
            downsampled_time.append(i * SAMPLE_PERIOD_SEC)

    # Tiến hành vẽ biểu đồ dạng bước từ tập dữ liệu đã làm sạch khoảng đè nét
    ax3.step(downsampled_time, downsampled_status, where='mid', color='#0984e3', linewidth=1.5)
    ax3.set_yticks([0, 1, 2, 3])
    ax3.set_yticklabels(['LEADS_OFF', 'NORMAL', 'TACHYCARDIA', 'BRADYCARDIA'], fontsize=9, weight='bold')
    ax3.set_title('BIẾN THIÊN TRẠNG THÁI THEO DÒNG THỜI GIAN (0.1s Resolution)', fontsize=12, fontweight='bold', color='#2d3748', pad=15)
    ax3.set_xlabel('Thời gian thực thi ca đo (Giây)', fontsize=10, color='#4a5568')
    ax3.grid(True, linestyle=':', alpha=0.6, color='#cbd5e1')

    # Ô 4 (Bottom-Right): Bảng thống kê chỉ số lâm sàng
    ax4 = axs[1, 1]
    ax4.axis('off')
    
    table_data = [
        ["Thông số hệ thống (Metrics)", "Giá trị thực tế (Value)"],
        ["Tổng thời gian ghi dữ liệu", f"{total_duration_sec:.2f} Giây"],
        ["Thời gian mất tín hiệu (Leads Off)", f"{leads_off_duration_sec:.2f} Giây"],
        ["Nhịp tim Trung bình (Avg BPM)", f"{avg_bpm:.1f} bpm" if avg_bpm > 0 else "0.0 bpm"],
        ["Nhịp tim Cao nhất (Max BPM)", f"{max_bpm:.1f} bpm" if max_bpm > 0 else "0.0 bpm"],
        ["Nhịp tim Thấp nhất (Min BPM)", f"{min_bpm:.1f} bpm" if min_bpm > 0 else "0.0 bpm"],
        ["Chỉ số HRV - SDNN (Độ ổn định tổng thể)", f"{sdnn_val:.2f} ms" if has_hrv else "0.00 ms"],
        ["Chỉ số HRV - RMSSD (Hệ đối giao cảm)", f"{rmssd_val:.2f} ms" if has_hrv else "0.00 ms"]
    ]
    
    table = ax4.table(cellText=table_data, loc='center', cellLoc='left')
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(0.9, 2.4)
    
    for key, cell in table.get_celld().items():
        cell.set_linewidth(0.5)
        cell.set_edgecolor('#cbd5e1')
        if key[0] == 0:
            cell.set_text_props(weight='bold', color='white', size=11)
            cell.set_facecolor('#0984e3') 
        else:
            cell.set_text_props(color='#2d3748')
            cell.set_facecolor('white')

    # Đổ tiêu đề lớn cho Dashboard phân tích tổng quát
    plt.suptitle(f'ECG ANALYSIS & HRV MEDICAL DASHBOARD', fontsize=16, fontweight='bold', color='#2d3748', y=0.97)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    
    # Lưu file ảnh chất lượng cao
    plt.savefig(OUTPUT_IMAGE_PATH, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"\n[SUCCESS] Đã tối ưu đồ thị trục thời gian. Dashboard mới xuất ra tại: '{OUTPUT_IMAGE_PATH}'")

if __name__ == "__main__":
    raw_data = load_raw_data(CSV_FILE_PATH)
    if raw_data is not None:
        generate_visual_dashboard(raw_data)
