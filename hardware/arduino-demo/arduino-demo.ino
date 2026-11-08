// Target: UNO Q + ULN2003 driver + 28BYJ-48 5V (driver still needs confirmation).
// Assumed hardware: confirm driver labels and external 5V supply before wiring.
// No automatic movement at startup. The scanner live demo sends n after each photo.
#include <Arduino.h>
#include <Arduino_RouterBridge.h>

const uint8_t MOTOR_PINS[4] = {8, 9, 10, 11}; // IN1, IN2, IN3, IN4 respectively
const uint8_t HALF_STEP[8][4] = {
  {1,0,0,0}, {1,1,0,0}, {0,1,0,0}, {0,1,1,0},
  {0,0,1,0}, {0,0,1,1}, {0,0,0,1}, {1,0,0,1}
};
// Nominal value only: internal gearbox ratios vary. Calibrate before imaging.
const uint32_t MOTOR_HALF_STEPS_PER_TURN = 4096;
const uint32_t TUBE_HALF_STEPS_PER_TURN = 2 * MOTOR_HALF_STEPS_PER_TURN;
const uint32_t START_INTERVAL_US = 8000;
const uint32_t RUN_INTERVAL_US = 4000;
uint32_t runIntervalUs = RUN_INTERVAL_US; // 1=original, 2=moderate, 3=fast test
const uint32_t RAMP_STEPS = 128;
const uint32_t SETTLE_MS = 500;

uint32_t remainingSteps = 0;
uint32_t completedSteps = 0;
uint32_t lastStepUs = 0;
uint32_t settleStartedMs = 0;
uint8_t phase = 7;
int8_t direction = 1;
bool settling = false;

void releaseMotor() {
  for (uint8_t i=0; i<4; ++i) digitalWrite(MOTOR_PINS[i], LOW);
}

void stopMotor() {
  remainingSteps = 0;
  settling = false;
  releaseMotor();
  Monitor.println("STOPPED: coils off. Position is not measured.");
}

void printHelp() {
  Monitor.println("28BYJ-48 test: motor is idle until a command is sent.");
  Monitor.println("j = short jog (~45 degrees at motor shaft)");
  Monitor.println("m = approximately one MOTOR shaft revolution");
  Monitor.println("t = approximately one TUBE revolution (two motor turns)");
  Monitor.println("r = reverse next movement; s = STOP and release; ? = help");
  Monitor.println("1 = original speed; 2 = moderate; 3 = fast TEST (select while idle)");
  Monitor.println("n = next 45-degree tube view; wait for DONE before taking a photo");
  Monitor.println("Test with NO gears/tubes first. Angles are open-loop estimates.");
}

void startMove(uint32_t steps) {
  if (remainingSteps || settling) {
    Monitor.println("BUSY: wait for DONE, or send s to stop.");
    return;
  }
  completedSteps = 0;
  remainingSteps = steps;
  lastStepUs = micros();
  Monitor.println("MOVING. Send s to stop.");
}

void handleCommand(char command) {
  switch (command) {
    case '1': case '2': case '3':
      if (remainingSteps || settling) Monitor.println("BUSY: stop or wait before changing speed.");
      else {
        runIntervalUs = command=='1' ? 4000 : command=='2' ? 3000 : 2000;
        Monitor.println(command=='1' ? "Original speed selected." :
                        command=='2' ? "Moderate speed selected; check for stalls." :
                                       "Fast TEST selected; revert if slipping or stalling.");
      }
      break;
    case 'n': case 'N': startMove(TUBE_HALF_STEPS_PER_TURN / 8); break;
    case 'j': case 'J': startMove(512); break;
    case 'm': case 'M': startMove(MOTOR_HALF_STEPS_PER_TURN); break;
    case 't': case 'T': startMove(TUBE_HALF_STEPS_PER_TURN); break;
    case 's': case 'S': stopMotor(); break;
    case 'r': case 'R':
      if (remainingSteps || settling) Monitor.println("Stop or wait before reversing.");
      else { direction = -direction; Monitor.println("Direction reversed for next move."); }
      break;
    case '?': printHelp(); break;
    case '\r': case '\n': case ' ': case '\t': break;
    default: Monitor.println("Unknown command. Send ? for help.");
  }
}

uint32_t stepIntervalUs() {
  uint32_t ramp = completedSteps;
  if (remainingSteps < ramp) ramp = remainingSteps;
  if (ramp > RAMP_STEPS) ramp = RAMP_STEPS;
  return START_INTERVAL_US - (START_INTERVAL_US-runIntervalUs)*ramp/RAMP_STEPS;
}

void updateMotor() {
  if (remainingSteps) {
    uint32_t now = micros();
    if ((uint32_t)(now-lastStepUs) < stepIntervalUs()) return;
    lastStepUs = now; // never burst steps to catch up after a delay
    phase = (uint8_t)((phase + (direction > 0 ? 1 : 7)) & 7);
    releaseMotor();
    for (uint8_t i=0; i<4; ++i)
      digitalWrite(MOTOR_PINS[i], HALF_STEP[phase][i] ? HIGH : LOW);
    --remainingSteps;
    ++completedSteps;
    if (!remainingSteps) {
      settling = true;
      settleStartedMs = millis();
      Monitor.println("Movement finished; settling for 0.5 s.");
    }
  } else if (settling && (uint32_t)(millis()-settleStartedMs) >= SETTLE_MS) {
    settling = false;
    releaseMotor();
    Monitor.println("DONE: coils off. Ready for next command.");
  }
}

void setup() {
  for (uint8_t i=0; i<4; ++i) {
    digitalWrite(MOTOR_PINS[i], LOW);
    pinMode(MOTOR_PINS[i], OUTPUT);
  }
  releaseMotor();
  Monitor.begin(115200);
  printHelp();
}

void loop() {
  for (uint8_t count=0; count<16 && Monitor.available(); ++count)
    handleCommand((char)Monitor.read());
  updateMotor();
}
