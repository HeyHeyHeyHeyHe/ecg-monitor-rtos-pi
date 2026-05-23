const int ecgPin = 36;  // SVP
const int LOPlus = 16;
const int LOMinus = 17;

float lowPass = 0.0;
float highPass = 0.0;

void setup() {
  Serial.begin(115200);
  pinMode(LOPlus, INPUT);
  pinMode(LOMinus, INPUT);
  Serial.println("=== ECG Raw Signal Test Started ===");
}

void loop() {
  if ((digitalRead(LOPlus) == 1) || (digitalRead(LOMinus) == 1)) {
    Serial.println("!");
  } else {
    int ecgValue = analogRead(ecgPin);
    lowPass = lowPass * 0.92 + ecgValue * 0.08;  // lowPass filter: baseline wander due to breathe
    highPass = ecgValue - lowPass;               // highPass: peaks
    Serial.println((int)(highPass * 8 + 2000));
  }
  delay(2);
}