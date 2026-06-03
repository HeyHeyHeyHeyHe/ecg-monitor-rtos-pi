#define ecgPin 36  // SVP (GPIO36)
const int LOPlus = 16;
const int LOMinus = 17;

enum HeartStatus {
  NORMAL = 0,
  BRADYCARDIA = 1, // Bradycardia (< 60 BPM)
  TACHYCARDIA = 2, // Tachycardia (> 100 BPM)
  LEADS_OFF = 3   
};

struct Package {
  int rawValue;
  int filteredValue;
  float bpm;
  HeartStatus status;
};

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

  rawEcgQueue = xQueueCreate(50, sizeof(int));
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

//Task 1
void TaskADC(void *pvParameters) {
  (void)pvParameters;
  for (;;) {
    int currentECG = 0;

    if ((digitalRead(LOPlus) == 0) && (digitalRead(LOMinus) == 0)) {
      currentECG = analogRead(ecgPin);
    } else {
      currentECG = -1;
    }

    xQueueSend(rawEcgQueue, &currentECG, 0);
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }
}
//Task 2
#define WINDOW_SIZE 6  //Moving average length

void TaskProcessECG(void *pvParameters) {
  (void)pvParameters;
  float lowPass = 0.0;
  float highPass = 0.0;
  unsigned long lastPeakTime = 0;
  unsigned long currentTime = 0;
  int threshold = 3800;  // Threshold for peak detection
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

  for (;;) {
    if (xQueueReceive(rawEcgQueue, &receivedRaw, portMAX_DELAY)) {
      currentTime = millis();
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

        if (filteredValue > threshold && filteredValue > lastValue) {
          unsigned long timeSinceLastPeak = currentTime - lastPeakTime;
          if (timeSinceLastPeak > 500) {
            lastPeakTime = currentTime;
            bpm = 60000.0 / timeSinceLastPeak;
          }
        }
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
        lowPass = 0.0; 
        prev_highPass = 0.0;
        moving_average_index = 0;
        moving_sum = 0.0;
        for (int i = 0; i < WINDOW_SIZE; i++) {
          moving_average_buffer[i] = 0.0;
        }
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

// Task 3
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
      
      switch(receivedData.status) {
        case NORMAL:      Serial.println("NORMAL"); break;
        case BRADYCARDIA: Serial.println("BRADYCARDIA"); break;
        case TACHYCARDIA: Serial.println("TACHYCARDIA"); break;
        case LEADS_OFF:   Serial.println("LEADS_OFF"); break;
    }
  }
}
}
