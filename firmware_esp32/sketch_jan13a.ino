const int ecgPin = 36;      // SVP
const int LOPlus = 16;
const int LOMinus = 17;

volatile int ecgValue = 0;
volatile bool newData = false;

float lowPass = 0.0;
float highPass = 0.0;

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
  
  Serial.println("=== ECG Week 2 - Day 3: Timer Interrupt 500Hz ===");
  Serial.println("Collecting sample 500 times/second...");
}

void loop() {
  if (newData) {
    int currentECG = ecgValue;
    newData = false;
    // Can add filter here 
    lowPass = lowPass * 0.92 + currentECG * 0.08;  // lowPass filter: baseline wander due to breathe
    highPass = currentECG - lowPass;               // highPass: peaks
    Serial.println((int)(highPass * 8 + 2000));
  }
}