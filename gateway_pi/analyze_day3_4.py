import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

CSV_FILE_PATH = "/home/pi/ecg_data_log.csv"
OUTPUT_IMAGE_PATH = "ecg_advanced_report.png"

def load_raw_data(file_path):
    if not os.path.exists(file_path):
        print(f"[ERROR] File not found at {file_path}.")
        return None
    
    # Read the 7-column file
    df = pd.read_csv(file_path)
    df['Status_String'] = df['Status_String'].astype(str).str.strip()
    df['BPM'] = pd.to_numeric(df['BPM'], errors='coerce')
    return df

def generate_visual_dashboard(df):
    total_rows = len(df)
    if total_rows == 0:
        print("[WARNING] CSV file contains no data.")
        return

    # --- 1. STATISTICAL & MATHEMATICAL COMPUTATION ---
    SAMPLE_PERIOD_SEC = 0.01  # 10ms sampling period per row
    total_duration_sec = total_rows * SAMPLE_PERIOD_SEC
    
    # Filter clean dataset for Heart Rate and HRV metrics (Exclude Leads Off and invalid BPM)
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
        # Convert BPM to RR intervals
        rr_intervals = 60000.0 / signal_df['BPM'].values
        
        # 1. Calculate SDNN (Standard Deviation of NN/RR intervals)
        sdnn_val = np.std(rr_intervals, ddof=1)
        
        # 2. Calculate RMSSD (Root Mean Square of Successive Differences)
        rr_diff = np.diff(rr_intervals) # RR_(n+1) - RR_n
        rmssd_val = np.sqrt(np.mean(rr_diff ** 2))
        has_hrv = True

    # --- 2. MODERN GRAPHICAL DESIGN (2x2 Grid Layout) ---
    plt.rcParams['font.family'] = 'sans-serif'
    fig, axs = plt.subplots(2, 2, figsize=(16, 10))
    fig.patch.set_facecolor('#f8fafc')

    # Define a unified color palette for both Pie Chart and Timeline Chart
    status_colors = {
        'NORMAL': '#00cec9',
        'TACHYCARDIA': '#ff7675',
        'BRADYCARDIA': '#fdcb6e',
        'LEADS_OFF': '#6c5ce7'
    }

    # Plot 1 (Top-Left): Clinical Metrics Summary Table
    ax1 = axs[0,0]
    ax1.axis('off')
    
    table_data = [
        ["System Metrics", "Value"],
        ["Total Data Logging Duration", f"{total_duration_sec:.2f} s"],
        ["Leads Off Duration", f"{leads_off_duration_sec:.2f} s"],
        ["Average Heart Rate (Avg BPM)", f"{avg_bpm:.1f} bpm" if avg_bpm > 0 else "0.0 bpm"],
        ["Maximum Heart Rate (Max BPM)", f"{max_bpm:.1f} bpm" if max_bpm > 0 else "0.0 bpm"],
        ["Minimum Heart Rate (Min BPM)", f"{min_bpm:.1f} bpm" if min_bpm > 0 else "0.0 bpm"],
        ["HRV Metric - SDNN", f"{sdnn_val:.2f} ms" if has_hrv else "0.00 ms"],
        ["HRV Metric - RMSSD", f"{rmssd_val:.2f} ms" if has_hrv else "0.00 ms"]
    ]
    
    table = ax1.table(cellText=table_data, loc='center', cellLoc='left')
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(0.9, 2.0) # Adjust vertical scaling to prevent clipping or text overlap
    
    for key, cell in table.get_celld().items():
        cell.set_linewidth(0.5)
        cell.set_edgecolor('#cbd5e1')
        if key[0] == 0:
            cell.set_text_props(weight='bold', color='white', size=11)
            cell.set_facecolor('#0984e3') 
        else:
            if key[0] in [6, 7]:
                cell.set_text_props(color='#2d3748', weight='bold')
                cell.set_facecolor('#eef2f7') # Highlight critical HRV metrics with a light gray background
            else:
                cell.set_text_props(color='#2d3748')
                cell.set_facecolor('white')
    ax1.set_title('CLINICAL METRICS SUMMARY', fontsize=12, fontweight='bold', color='#2d3748', pad=5)

    # Plot 2 (Top-Right): Poincare Plot (Valid RR Intervals Only)
    ax2 = axs[0, 1]
    ax2.set_facecolor('white')
    
    if has_hrv:
        rr_intervals = 60000.0 / signal_df['BPM'].values
        x_rr = rr_intervals[:-1]
        y_rr = rr_intervals[1:]
        
        ax2.scatter(x_rr, y_rr, color='#6c5ce7', alpha=0.6, edgecolors='none', s=25, label='RR Pairs ($RR_n / RR_{n+1}$)')
        min_val, max_val = min(rr_intervals) - 30, max(rr_intervals) + 30
        ax2.set_xlim(min_val, max_val)
        ax2.set_ylim(min_val, max_val)
    else:
        ax2.text(0.5, 0.5, 'SIGNAL LOST\n(Awaiting ESP32 connection...)', 
                 horizontalalignment='center', verticalalignment='center', 
                 transform=ax2.transAxes, fontsize=12, color='#e74c3c', weight='bold')
        min_val, max_val = 400, 1200
        ax2.set_xlim(min_val, max_val)
        ax2.set_ylim(min_val, max_val)

    ax2.plot([min_val, max_val], [min_val, max_val], color='#e17055', linestyle='--', linewidth=1.5, label='Identity Line ($RR_n = RR_{n+1}$)')
    ax2.set_title('POINCARÉ PLOT FOR HEART RATE VARIABILITY (HRV)', fontsize=12, fontweight='bold', color='#2d3748', pad=15)
    ax2.set_xlabel('$RR_n$ (Current Interval - ms)', fontsize=10, color='#4a5568')
    ax2.set_ylabel('$RR_{n+1}$ (Next Interval - ms)', fontsize=10, color='#4a5568')
    ax2.grid(True, linestyle=':', alpha=0.6, color='#cbd5e1')
    ax2.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='#e2e8f0')

    # Plot 3 (Bottom-Left): Status Variation Timeline (Step Plot)
    ax3 = axs[1, 0]
    ax3.set_facecolor('white')
    
    status_mapping = {'NORMAL': 1, 'TACHYCARDIA': 2, 'BRADYCARDIA': 3, 'LEADS_OFF': 0}
    
    # Downsampling Algorithm: Group every 10 log rows (~0.1s blocks) into the most frequent status
    STEP_SIZE = 10  
    downsampled_status = []
    downsampled_time = []
    
    for i in range(0, total_rows, STEP_SIZE):
        block = df['Status_String'].iloc[i : i + STEP_SIZE]
        if not block.empty:
            most_frequent = block.value_counts().idxmax()
            downsampled_status.append(status_mapping.get(most_frequent, 0))
            downsampled_time.append(i * SAMPLE_PERIOD_SEC)

    ax3.step(downsampled_time, downsampled_status, where='mid', color='#0984e3', linewidth=1.5, label='Status Path')
    ax3.set_yticks([0, 1, 2, 3])
    ax3.set_yticklabels(['LEADS_OFF', 'NORMAL', 'TACHYCARDIA', 'BRADYCARDIA'], fontsize=9, weight='bold')
    ax3.set_title('STATUS VARIATION OVER TIME (0.1s Resolution)', fontsize=12, fontweight='bold', color='#2d3748', pad=15)
    ax3.set_xlabel('Elapsed Time (Seconds)', fontsize=10, color='#4a5568')
    ax3.grid(True, linestyle=':', alpha=0.6, color='#cbd5e1')
    ax3.legend(loc='upper right', frameon=True, facecolor='white', edgecolor='#e2e8f0')

    # Plot 4 (Bottom-Right): Clinical Status Distribution Pie Chart
    ax4 = axs[1,1]
    ax4.set_facecolor('#f8fafc')
    status_counts = df['Status_String'].value_counts()
    
    # Dynamically match colors with existing clinical states in the current run
    current_palette = [status_colors.get(status, '#74b9ff') for status in status_counts.index]
    
    wedges, texts, autotexts = ax4.pie(
        status_counts.values, labels=status_counts.index, autopct='%1.1f%%', 
        startangle=135, colors=current_palette,
        wedgeprops={'edgecolor': '#f8fafc', 'linewidth': 2, 'antialiased': True}
    )
    plt.setp(autotexts, size=10, weight="bold", color="white")
    plt.setp(texts, size=10, color='#2d3748')
    ax4.set_title('CLINICAL STATUS DISTRIBUTION', fontsize=12, fontweight='bold', color='#2d3748', pad=10)

    # Supertitle setup for the entire analytical dashboard layout
    plt.suptitle(f'ECG ANALYSIS & HRV MEDICAL DASHBOARD', fontsize=16, fontweight='bold', color='#2d3748', y=0.97)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    
    # Save the chart output
    plt.savefig(OUTPUT_IMAGE_PATH, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"\n[SUCCESS] Advanced visual dashboard exported at: '{OUTPUT_IMAGE_PATH}'")

if __name__ == "__main__":
    raw_data = load_raw_data(CSV_FILE_PATH)
    if raw_data is not None:
        generate_visual_dashboard(raw_data)
