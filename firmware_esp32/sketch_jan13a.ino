const int ecgPin = 36;      // SVP
const int LOPlus = 16;
const int LOMinus = 17;

volatile int ecgValue = 0;
volatile bool newData = false;

float lowPass = 0.0;
float highPass = 0.0;

unsigned long lastBeatTime = 0;
unsigned long firstBeatTime = 0;
int bpm = 0;
int beatCount = 0;
const int threshold = 3800;

void IRAM_ATTR onTimer() {
  // Check Leads-off
  if ((digitalRead(LOPlus) == 0) && (digitalRead(LOMinus) == 0)) {
    ecgValue = analogRead(ecgPin);
    newData = true;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LOPlus, INPUT);
  pinMode(LOMinus, INPUT);
  
  // Setup for Timer Interrupt
  hw_timer_t * timer = timerBegin(0, 80, true);     // Timer 0, prescaler 80
  timerAttachInterrupt(timer, &onTimer, true);
  timerAlarmWrite(timer, 2000, true);               // 2000us = 500Hz
  timerAlarmEnable(timer);
  
  Serial.println("=== ECG Week 2 ===");
  Serial.println("Collecting sample 500 times/second...");
}

void loop() {
  if (newData) {
    int currentECG = ecgValue; 
    newData = false;
    // Can add filter here 
    lowPass = lowPass * 0.92 + currentECG * 0.08;  // lowPass filter: baseline wander due to breathe
    highPass = currentECG - lowPass;               // highPass: peaks
    int filteredValue = (int)(highPass * 8 + 2000);

    // Calculate Bpm 
    static bool insidePeak = false; 

    if (filteredValue > threshold) {
      if (!insidePeak && (millis() - lastBeatTime > 350)) { //detect peaks
        insidePeak = true; 
        if (beatCount == 0) {
          firstBeatTime = millis(); // Record the first beat in real time 
        }
        lastBeatTime = millis();
        beatCount++;
        if (beatCount >= 5) {  
          unsigned long totalDuration = lastBeatTime - firstBeatTime;
          if (totalDuration > 0) {
            // Algorithm: (number of times between beats * 60000) / total duration 
            int calculatedBpm = (4 * 60000) / totalDuration;
            if (calculatedBpm >= 50 && calculatedBpm <= 140) {
              bpm = calculatedBpm;
            }
          }
          firstBeatTime = lastBeatTime;
          beatCount = 1;
        }
      }
    } else {
      insidePeak = false; 
    }

    // Results on Serial Monitor: Filtered Ecg value , Bpm value 
    Serial.print(filteredValue);
    Serial.print(",");
    Serial.println(bpm);
  }
}