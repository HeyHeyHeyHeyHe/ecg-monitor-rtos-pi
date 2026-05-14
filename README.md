# ECG Real-time Monitoring System (RTOS + Raspberry Pi)

## Overview
Real-time electrocardiogram monitoring system using ESP32 FreeRTOS and Raspberry Pi

Hệ thống giám sát điện tâm đồ thời gian thực sử dụng FreeRTOS trên ESP32 để thu thập dữ liệu và Raspberry Pi làm Gateway xử lý.

## [cite_start]Architecture [cite: 37]
[cite_start][Dán sơ đồ ASCII từ file Work flow.docx của bạn vào đây] [cite: 37, 66]

## Tech Stack
- [cite_start]**Firmware:** ESP32, FreeRTOS, C++, ADC sampling (500Hz) [cite: 22, 70]
- [cite_start]**Gateway:** Raspberry Pi, Python, UART communication [cite: 27, 71]
- [cite_start]**Web:** Flask, WebSockets, Chart.js [cite: 28, 30]