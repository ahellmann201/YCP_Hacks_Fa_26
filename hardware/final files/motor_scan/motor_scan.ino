// Automatic three-tube scanner: UNO Q, 28BYJ-48 5 V, ULN2003 IN1..4 on D8..D11.
// Separate from motor_test.ino. No movement at startup; all commands are bounded.
#include <Arduino.h>
#include <Arduino_RouterBridge.h>

// Safe RPC handlers run in the sketch loop hook, avoiding cross-thread motor state access.
const uint8_t pins[4]={8,9,10,11};
const uint8_t phases[8][4]={
  {1,0,0,0},{1,1,0,0},{0,1,0,0},{0,1,1,0},
  {0,0,1,0},{0,0,1,1},{0,0,0,1},{1,0,0,1}
};
// Nominal 8192 half steps/tube turn with the printed 20:40 gear ratio.
const uint32_t viewSteps=1024, rampSteps=128, settleMs=500;
int commandId=0, motorState=0; // 0 idle, 1 moving, 2 settling, 3 done, 4 stopped
uint32_t remaining=0, completed=0, intervalUs=4000;
uint32_t lastStep=0, lastContact=0, movementStarted=0, settlingStarted=0;
uint8_t phase=7;

void coilsOff() { for(uint8_t pin:pins) digitalWrite(pin,LOW); }
void stopLocked() { remaining=0; coilsOff(); motorState=4; }

int scannerMove(int id,int speed) {
  int result=0;
  if(id>0 && id==commandId) result=motorState==4 ? -2 : 1;
  else if(id>commandId && speed>=1 && speed<=3 && motorState!=1 && motorState!=2) {
    commandId=id; intervalUs=speed==1?4000:speed==2?3000:2000;
    remaining=viewSteps; completed=0; lastStep=micros();
    lastContact=movementStarted=millis(); motorState=1; result=1;
  }
  return result;
}

String scannerStatus() {
  lastContact=millis();
  String result=String("{\"protocol\":1,\"id\":")+String(commandId)+
    ",\"state\":"+String(motorState)+",\"remaining\":"+String(remaining)+"}";
  return result;
}

bool scannerStop() {
  stopLocked();
  return true;
}

void setup() {
  for(uint8_t pin:pins) { digitalWrite(pin,LOW); pinMode(pin,OUTPUT); }
  coilsOff();
  if(!Bridge.begin()) return;
  if(!Bridge.provide_safe("scanner_status",scannerStatus) ||
     !Bridge.provide_safe("scanner_move",scannerMove) ||
     !Bridge.provide_safe("scanner_stop",scannerStop)) scannerStop();
}

void loop() {
  uint32_t nowMs=millis();
  if((motorState==1 || motorState==2) &&
     ((uint32_t)(nowMs-lastContact)>1500 || (uint32_t)(nowMs-movementStarted)>15000)) {
    stopLocked(); // Loss of controller heartbeat cannot leave the motor running.
  } else if(motorState==1) {
    uint32_t ramp=completed;
    if(remaining<ramp) ramp=remaining;
    if(ramp>rampSteps) ramp=rampSteps;
    uint32_t delayUs=8000-(8000-intervalUs)*ramp/rampSteps;
    uint32_t now=micros();
    if((uint32_t)(now-lastStep)>=delayUs) {
      lastStep=now; phase=(phase+1)&7;
      for(uint8_t i=0;i<4;i++) digitalWrite(pins[i],phases[phase][i]?HIGH:LOW);
      --remaining; ++completed;
      if(!remaining) { motorState=2; settlingStarted=nowMs; }
    }
  } else if(motorState==2 && (uint32_t)(nowMs-settlingStarted)>=settleMs) {
    coilsOff(); motorState=3; // DONE means the settling pause has also completed.
  }
}
