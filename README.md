# Real-Time ECG Monitoring System

A robust, 3-tier real-time Electrocardiogram (ECG) monitoring system utilizing an **ESP32 (FreeRTOS)** for edge processing, a **Raspberry Pi** as an IoT gateway, and an interactive **Web Dashboard** for real-time visualization and analytics.

---

## 📌 Project Overview

This project implements a medical prototype designed to capture analog ECG signals, perform real-time digital signal processing (DSP) at the edge, transmit telemetry reliably, and provide clinical-grade visualizations.

* **Target Hardware**: ESP32-WROOM-32D, AD8232 ECG Sensor, Raspberry Pi 4.
* **Key Features**: High-frequency sampling, real-time QRS detection, dynamic Heart Rate (BPM) calculation, interactive web dashboard, Heart Rate Variability (HRV) analysis, and auto-generated PDF clinical reports.

---

## System Architecture (3-Tier)

* **Block Diagram**:
  
  The system is decoupled into three distinct layers to optimize real-time constraints and compute distribution:
  
  ```mermaid
  ---
  config:
    layout: elk
  ---
  flowchart LR
  subgraph subGraph0["Tier 1: Edge Computing (ESP32)"]
          B["ESP32 + FreeRTOS"]
    end
  subgraph subGraph1["Tier 2: IoT Gateway (Raspberry Pi)"]
          C["Raspberry Pi Gateway"]
          E["HRV Analysis & PDF Generator"]
    end
  subgraph subGraph2["Tier 3: Visualization & Analytics"]
          D["Web Dashboard"]
    end
      A["AD8232 Sensor + ECG Electrodes"] -- Analog Signal --> B
      B -- UART Serial Data --> C
      C -- WebSockets --> D
      C -- Python Engine --> E

      style B fill:#f9f,stroke:#333,stroke-width:2px
      style C fill:#bbf,stroke:#333,stroke-width:2px
      style D fill:#f96,stroke:#333,stroke-width:2px
  ```

  1. Tier 1: Edge Computing (ESP32)
  - Sampling: Reads the AD8232 analog output using a hardware timer interrupt.

  - Multi-Tasking: Powered by FreeRTOS with dedicated tasks:

    TaskADC: High-priority task managing ADC conversion.

    TaskProcessECG: Runs a real-time Pan-Tompkins QRS detection algorithm to identify heartbeats and compute real-time BPM.

    TaskSerialPrint: Packetizes data and streams raw signal + BPM over UART.

  2. Tier 2: IoT Gateway (Raspberry Pi)
  - Data Ingestion: A background service (uart_reader.py) monitors the serial port, parses incoming data packets, and logs them into a rolling CSV database.

  - Application Server: A Flask web server (app.py) integrated with Flask-SocketIO to broadcast live data points to the client.

  - Analytics: A dedicated analysis script (analyze_day3_4.py) parses accumulated data, extracts Heart Rate Variability (HRV) metrics, generates plots, and compiles a comprehensive PDF report. 

  3. Tier 3: Visualization & Analytics
  - Real-time Charting: Renders live ECG waveforms smoothly using Chart.js.

  - Interactive UI: Clean, responsive dashboard designed in HTML/CSS (templates/index.html) featuring gauge meters for BPM, status alerts, and report generation controls. 
  
* **AD8232 ESP32 Connection**: 

  ```mermaid
  graph LR
    subgraph "ESP32-WROOM-32D"
        GPIO36[GPIO36\nSVP]
        GPIO16[GPIO16]
        GPIO17[GPIO17]
        V33[3.3V]
        GND1[GND]
    end

    subgraph "AD8232 Heart Monitor"
        AD[AD8232 Board]
        Electrodes[ECG Electrodes\nRA - LA - RL]
    end

    Electrodes --> AD

    AD -->|"OUTPUT"| GPIO36
    AD -->|"LO+"| GPIO16
    AD -->|"LO-"| GPIO17
    AD -->|"3.3V"| V33
    AD -->|"GND"| GND1

    style AD fill:#e74c3c,stroke:#333
    style GPIO36 fill:#27ae60,stroke:#333
    style GPIO16 fill:#f39c12,stroke:#333
    style GPIO17 fill:#9b59b6,stroke:#333
    style V33 fill:#f1c40f,stroke:#333

    linkStyle 0 stroke:#27ae60,stroke-width:3px
    linkStyle 1 stroke:#f39c12,stroke-width:3px
    linkStyle 2 stroke:#9b59b6,stroke-width:3px
    linkStyle 3 stroke:#f1c40f,stroke-width:3px
  ```

* **ESP32 Raspberry Pi Connection**: 

  ```mermaid
  graph LR
    subgraph "ESP32-WROOM-32D"
        GPIO4[GPIO4\nTX]
        GPIO5[GPIO5\nRX]
        GND1[GND]
    end

    subgraph "Raspberry Pi 4"
        GPIO14[GPIO14\nTX]
        GPIO15[GPIO15\nRX]
        GND2[GND]
    end

    GPIO4 -->|"TX"| GPIO15
    GPIO5 -->|"RX"| GPIO14
    GND1 -->|"GND"| GND2

    style GPIO4 fill:#27ae60,stroke:#333
    style GPIO5 fill:#9b59b6,stroke:#333
    style GPIO14 fill:#f39c12,stroke:#333
    style GPIO15 fill:#f1c40f,stroke:#333

    linkStyle 0 stroke:#27ae60,stroke-width:3px
    linkStyle 1 stroke:#9b59b6,stroke-width:3px
  ```

---

## Engineering Insight: Signal Filtering 

During the initial deployment, the raw analog signal captured by the front-end amplifier retained the general geometric morphology of the **QRS complex**. However, it suffered from severe **high-frequency noise** and **baseline wander** (induced by powerline interference and minor motion artifacts). This raw data stream significantly compromised the peak-detection accuracy, leading to false positives and highly erratic BPM calculations.

To address this, a digital filtering pipeline was implemented:

* **Before Filtering:** Jagged high-frequency ripples obscured the fine details of the waveform, making precise R-peak identification mathematically unreliable. 

  (image)
  
* **After Filtering:** The implemented digital filters effectively attenuated out-of-band noise, isolating a clean, stabilized baseline. The resulting waveform presents distinct, well-defined R-peaks with smooth, prominent upward deflections. This stark contrast drastically simplifies threshold-based peak detection, ensuring highly stable and accurate real-time Heart Rate (BPM) computations.

  (image)

---

## How the R-R Interval Works

* **Definition**:

  The **R-R Interval** is the exact duration (expressed in milliseconds) between the peaks of two consecutive **R-waves** (the highest voltage spikes in the QRS complex of an ECG signal). 

  In embedded biomedical systems, this metric forms the computational baseline for calculating dynamic heart metrics.

* **Mathematical Equation**:

  The edge processor (ESP32) isolates the time difference ($\Delta T$) between successive threshold-crossing R-peaks to compute the instantaneous **Beats Per Minute (BPM)**:

  $$\text{BPM} = \frac{60,000}{\text{R-R Interval (ms)}}$$

---

## Getting Started
Follow these instructions to set up and run the entire system locally.

### **Prerequisites**:
  - PlatformIO IDE installed (VS Code extension recommended).

  - Raspberry Pi with Python 3.8+ installed.

  - Hardware connections completed: AD8232 -> ESP32 -> Raspberry Pi.

### **Step 1**: Flash the ESP32 Firmware
  - Connect your ESP32 to your development machine.

  - Open the firmware folder in VS Code with PlatformIO.

  - Build and upload the firmware

### **Step 2**: Set Up the Raspberry Pi Gateway
  - Flash SD card for Raspberry Pi 

  - Enable UART on Raspberry Pi 

  - Create and activate a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

  - Install the required dependencies:
    - Flask==3.0.2
    - Flask-SocketIO==5.3.6
    - pyserial==3.5
    - numpy==1.26.4
    - pandas==2.2.1
    - matplotlib==3.8.3
    - reportlab==4.1.0

  - Get all the files in gateway_pi folder onto Raspberry Pi 

### **Step 3**: Run the Services
  You will need two active terminal sessions inside your virtual environment (source venv/bin/activate):

  - Terminal 1: Start the UART Reader 

```bash
python3 uart_reader.py
```

  - Terminal 2: Start the Web Dashboard Server

```bash
python3 app.py
```

  Open your browser and navigate to `http://<your_raspberry_pi_ip>:5000` to view the live stream.

---

## 📊 Results & Demo

* **Real-time Waveform Rendering and Web Dashboard Overview**
  
  Below is the processed, clean ECG signal outputting live on the web dashboard: 
  
  (video)

* **Physical Implementation**
  
  Below is the physical hardware assembly showing the interconnected computing tiers and sensor routing:
  
  (image)

* **Report**
  
  Report form: 
  
  (image)

* **Demo**

  Below is the demo video: 
  *Note: Minor video lag is primarily caused by host machine overheating (thermal throttling) and full-resolution screen rendering.*

  (video)

---

## Lessons Learned

* **Embedded Systems & RTOS**: ESP32 utilizing C++, PlatformIO, FreeRTOS. 

* **Digital Signal Processing (DSP)**: Digital Bandpass Filter and real-time peak-detection logic.
  
* **IoT Gateways & Protocols**: UART Serial Communication, and WebSockets (Socket.IO).
  
* **Backend & Data Engineering**: Raspberry Pi using Python. 
  
* **Data Analytics & Clinical Reporting**: NumPy, Pandas, and Matplotlib to parse aggregated time-series data for Heart Rate Variability (HRV) metrics, and ReportLab PNG.
  
* **Frontend Data Visualization**: Chart.js, HTML, and CSS.

---

## Future Improvements

* **Wireless Telemetry**: Transition from wired UART to Bluetooth Low Energy (BLE) or MQTT over Wi-Fi for patient mobility.
* **Time-Series Database**: Replace the rolling CSV setup with InfluxDB or TimescaleDB for efficient high-frequency logging.
* **Cloud Scaling**: Integrate an AWS IoT Core or MQTT broker to support multiple concurrent patient streams.

---

## Resources

### Core Technologies & Official Documentation
- **ESP32 Technical Reference Manual**:  
  [Espressif ESP32 TRM](https://www.espressif.com/sites/default/files/documentation/esp32_technical_reference_manual_en.pdf)

- **Arduino-ESP32 Core**:  
  [GitHub - espressif/arduino-esp32](https://github.com/espressif/arduino-esp32)

- **Raspberry Pi UART & Flask-SocketIO**:  
  [Raspberry Pi Documentation - UART](https://www.raspberrypi.com/documentation/computers/configuration.html#configuring-uarts)  
  [Flask-SocketIO](https://flask-socketio.readthedocs.io/)

### Learning Resources
- FreeRTOS: [DigiKey - Introduction to RTOS course (12 videos)](https://youtu.be/F321087yYy4?si=iEa-WaJJoItqxhHM) 
- Biomedical Signal Processing references (ECG filtering & QRS detection) 
- Biomedical Metrics references (BPM, HRV)
