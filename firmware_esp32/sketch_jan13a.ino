#define ecgPin 36  // SVP (GPIO36)
const int LOPlus = 16;
const int LOMinus = 17;

struct Package {
  int filteredValue;
  float bpm;
};
QueueHandle_t ecgQueue;

void TaskProcessECG(void *pvParameters);
void TaskSerialPrint(void *pvParameters);

void setup() {
  Serial.begin(115200);
  pinMode(LOPlus, INPUT);
  pinMode(LOMinus, INPUT);
  pinMode(ecgPin, INPUT);

  ecgQueue = xQueueCreate(50, sizeof(Package));

  if (ecgQueue != NULL) {
    xTaskCreatePinnedToCore(
      TaskProcessECG,
      "ProcessECG",
      4096,
      NULL,
      3,
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

//Task1
void TaskProcessECG(void *pvParameters) {
  (void)pvParameters;
  float lowPass = 0.0;
  float highPass = 0.0;
  unsigned long lastPeakTime = 0;
  unsigned long currentTime = 0;
  int threshold = 3800;  // Threshold for peak detection
  int lastValue = 0;
  int filteredValue=0;
  float bpm=0.0;

  for (;;) {
    currentTime = millis();
    if ((digitalRead(LOPlus) == 0) && (digitalRead(LOMinus) == 0)) {
      int currentECG = analogRead(ecgPin);
      
      lowPass = lowPass * 0.92 + currentECG * 0.08;
      highPass = currentECG - lowPass;
      filteredValue = (int)(highPass * 8 + 2000);

      if (filteredValue > threshold && filteredValue > lastValue) {
        unsigned long timeSinceLastPeak = currentTime - lastPeakTime;
        if (timeSinceLastPeak > 500) {
          lastPeakTime = currentTime;
          bpm = 60000.0 / timeSinceLastPeak;  
        }
      }
      lastValue = filteredValue;
    } else {
      filteredValue=0;
      if (currentTime - lastPeakTime > 4000) {
        bpm = 0.0; 
    }} 
    if (currentTime - lastPeakTime > 3000 && bpm > 0.0) {
      bpm = 0.0;
    }
    Package dataToSend;
    dataToSend.filteredValue = filteredValue;
    dataToSend.bpm = bpm;

    xQueueSend(ecgQueue, &dataToSend, 0);
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }
}

// Task 2
void TaskSerialPrint(void *pvParameters) {
  (void)pvParameters;
  Package receivedData;

  for (;;) {
    if (xQueueReceive(ecgQueue, &receivedData, portMAX_DELAY)) {
      Serial.print(receivedData.filteredValue);
      Serial.print(",");
      Serial.println(receivedData.bpm);
    }
  }
}
