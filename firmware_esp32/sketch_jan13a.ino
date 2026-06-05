#define ecgPin 36        // SVP (GPIO36)
const int LOPlus = 16;   // Leads-off detection positive pin
const int LOMinus = 17;  // Leads-off detection negative pin

enum HeartStatus {
  NORMAL = 0,
  BRADYCARDIA = 1,  // Bradycardia (< 60 BPM)
  TACHYCARDIA = 2,  // Tachycardia (> 100 BPM)
  LEADS_OFF = 3
};

struct EcgSample {
  int value;
  unsigned long timestamp;
};

struct Package {
  int rawValue;
  int filteredValue;
  float bpm;
  HeartStatus status;
};
// FreeRTOS Queue Handles
QueueHandle_t rawEcgQueue;
QueueHandle_t processedQueue;

void TaskADC(void *pvParameters);
void TaskProcessECG(void *pvParameters);
void TaskSerialPrint(void *pvParameters);

void setup() {
  Serial.begin(115200);
  pinMode(LOPlus, INPUT);
  pinMode(LOMinus, INPUT);
  pinMode(ecgPin, INPUT);
  // Initialize FreeRTOS Queues (Capacity: 50 elements each)
  rawEcgQueue = xQueueCreate(50, sizeof(EcgSample));
  processedQueue = xQueueCreate(50, sizeof(Package));

  if (rawEcgQueue != NULL && processedQueue != NULL) {
    Serial.println("Timestamp(ms),Raw_Value,Filtered_Value,BPM,Status");
    xTaskCreatePinnedToCore(TaskADC, "TaskADC", 2048, NULL, 3, NULL, 1);
    xTaskCreatePinnedToCore(
      TaskProcessECG,
      "ProcessECG",
      4096,
      NULL,
      2,
      NULL,
      1);

    xTaskCreatePinnedToCore(
      TaskSerialPrint,
      "SerialPrint",
      2048,
      NULL,
      1,
      NULL,
      1);
  } else {
    Serial.println("Error creating the queue");
  }
}

void loop() {
  vTaskDelay(1000 / portTICK_PERIOD_MS);
}

/**
 * @brief TASK 1: Data acquisition (ADC sampling)
 * @details Samples the analog ECG pin at a deterministic 100Hz frequency (10ms intervals)
 * while managing physical leads-off hardware tracking checks.
 */
void TaskADC(void *pvParameters) {
  (void)pvParameters;
  for (;;) {
    EcgSample sample;
    sample.timestamp = millis();

    // Check Leads-off before reading analog value
    if ((digitalRead(LOPlus) == 0) && (digitalRead(LOMinus) == 0)) {
      sample.value = analogRead(ecgPin);
    } else {
      sample.value = -1;  // Flag indicating electrode disconnection
    }
    xQueueSend(rawEcgQueue, &sample, 0);
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }
}
/**
 * @brief TASK 2: Signal processing 
 * @details Implements an integrated real-time QRS detection engine
 * enhanced with an automated Adaptive Threshold. 
 */
#define WINDOW_SIZE 6  //Moving average length

void TaskProcessECG(void *pvParameters) {
  (void)pvParameters;
  EcgSample receivedSample;
  float lowPass = 0.0;
  float highPass = 0.0;
  unsigned long lastPeakTime = 0;
  unsigned long currentTime = 0;
  int lastValue = 0;
  int filteredValue = 0;
  float bpm = 0.0;
  int receivedRaw = 0;
  HeartStatus currentStatus = NORMAL;

  // Filter variables
  static float prev_highPass = 0.0;
  static float moving_average_buffer[WINDOW_SIZE] = { 0 };
  static int moving_average_index = 0;
  static float moving_sum = 0.0;
  float derivative = 0.0;
  float squared = 0.0;

  // Variables for adaptive threshold
  float signalLevel = 57000.0;  // estimate for true QRS peak power
  float noiseLevel = 750.0;
  float threshold = 15000.0;  // initial threshold
  int localMax = 0;
  static bool peakStateRecorded = false;  // Flag to check whether the peak is recorded
  for (;;) {
    if (xQueueReceive(rawEcgQueue, &receivedSample, portMAX_DELAY)) {
      currentTime = receivedSample.timestamp; 
      receivedRaw = receivedSample.value; 
      if (receivedRaw != -1) {
        //Baseline wander removal (high-pass)
        lowPass = lowPass * 0.92 + receivedRaw * 0.08;
        highPass = (float)receivedRaw - lowPass;

        //Derivative Filter
        derivative = highPass - prev_highPass;  //getting slope
        prev_highPass = highPass;

        //Squaring (squaring to spot QRS peaks, eliminate noise and T, P waveform)
        squared = (derivative * derivative) * 0.1;

        // Moving Average Filter
        moving_sum -= moving_average_buffer[moving_average_index];
        moving_average_buffer[moving_average_index] = squared;
        moving_sum += squared;
        moving_average_index = (moving_average_index + 1) % WINDOW_SIZE;
        filteredValue = (int)(moving_sum / (float)WINDOW_SIZE);

        // Adaptive threshold + Bpm calculation
        if (filteredValue > (int)threshold) {
          // Identify local maximum point
          if (filteredValue < lastValue && !peakStateRecorded) {
            localMax = lastValue;
            // Update values for bpm and signalLevel
            unsigned long timeSinceLastPeak = currentTime - lastPeakTime;
            if (timeSinceLastPeak > 500) {
              lastPeakTime = currentTime;
              bpm = 60000.0 / timeSinceLastPeak;
              signalLevel = 0.125 * (float)localMax + 0.875 * signalLevel;
              peakStateRecorded = true;
            }
          }
        } else {  // Post-peak exit phase
          if (peakStateRecorded) {
            // Reset variables
            peakStateRecorded = false;
            localMax = 0;
          }
          if (filteredValue < (int)(threshold * 0.5)) {
            float temp_noise = 0.125 * (float)filteredValue + 0.875 * noiseLevel;
            // prevent noiseLevel to be higher than 8% signalLevel 
            if (temp_noise < (signalLevel * 0.08)) {
              noiseLevel = temp_noise;
            } else {
              noiseLevel = signalLevel * 0.08;
            }
          }
        }
        threshold = noiseLevel + 0.25 * (signalLevel - noiseLevel);

        // Detect anomal signal
        if (currentTime - lastPeakTime > 3500) {
          bpm = 0.0;
          currentStatus = BRADYCARDIA;
        } else if (bpm > 0.0 && bpm < 60.0) {
          currentStatus = BRADYCARDIA;
        } else if (bpm > 100.0) {
          currentStatus = TACHYCARDIA;
        } else if (bpm >= 60.0 && bpm <= 100.0) {
          currentStatus = NORMAL;
        }
        lastValue = filteredValue;
      } else {
        filteredValue = 0;
        if (currentTime - lastPeakTime > 4000) {
          bpm = 0.0;
        }
        currentStatus = LEADS_OFF;
        // Reset
        lowPass = 0.0;
        prev_highPass = 0.0;
        moving_average_index = 0;
        moving_sum = 0.0;
        for (int i = 0; i < WINDOW_SIZE; i++) {
          moving_average_buffer[i] = 0.0;
        }
        peakStateRecorded = false;
        localMax = 0;
        signalLevel = 57000.0;
        noiseLevel = 750.0;
        threshold = 15000.0;
      }
      Package dataToSend;
      dataToSend.rawValue = receivedRaw;
      dataToSend.filteredValue = filteredValue;
      dataToSend.bpm = bpm;
      dataToSend.status = currentStatus;
      xQueueSend(processedQueue, &dataToSend, 0);
    }
  }
}
/**
 * @brief TASK 3: Output 
 * @details Dequeues and prints processed ECG data package to the Serial Monitor.  
 */
void TaskSerialPrint(void *pvParameters) {
  (void)pvParameters;
  Package receivedData;

  for (;;) {
    if (xQueueReceive(processedQueue, &receivedData, portMAX_DELAY)) {
      Serial.print(millis());
      Serial.print(",");
      Serial.print(receivedData.rawValue);
      Serial.print(",");
      Serial.print(receivedData.filteredValue);
      Serial.print(",");
      Serial.print(receivedData.bpm, 1);
      Serial.print(",");

      switch (receivedData.status) {
        case NORMAL: Serial.println("NORMAL"); break;
        case BRADYCARDIA: Serial.println("BRADYCARDIA"); break;
        case TACHYCARDIA: Serial.println("TACHYCARDIA"); break;
        case LEADS_OFF: Serial.println("LEADS_OFF"); break;
      }
    }
  }
}
