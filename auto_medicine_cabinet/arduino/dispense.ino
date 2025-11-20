// Auto Medicine Cabinet dispenser firmware
// Listens for serial commands A, B, C, or D and toggles relays on pins 5-8

const int relayPins[4] = {5, 6, 7, 8};
const int pulseMs = 300;

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) {
    pinMode(relayPins[i], OUTPUT);
    digitalWrite(relayPins[i], LOW);
  }
}

void pulseRelay(int idx) {
  digitalWrite(relayPins[idx], HIGH);
  delay(pulseMs);
  digitalWrite(relayPins[idx], LOW);
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    switch (cmd) {
      case 'A':
        pulseRelay(0);
        break;
      case 'B':
        pulseRelay(1);
        break;
      case 'C':
        pulseRelay(2);
        break;
      case 'D':
        pulseRelay(3);
        break;
      default:
        break;
    }
  }
}
