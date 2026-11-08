// Host simulation of the real sketch. Not an UNO Q core compilation or hardware test.
#include <cassert>
#include <iostream>
#include "Arduino.h"
#include "Arduino_RouterBridge.h"
uint64_t simulatedUs=0;
int simulatedPins[32]={};
SimulatedMonitor Monitor;
#include "../final files/motor_test/motor_test.ino"

bool allOff() {
  for(auto pin:MOTOR_PINS) if(simulatedPins[pin]) return false;
  return true;
}
void send(char c) { Monitor.input.push_back(c); loop(); }
void advance(uint32_t us) { simulatedUs+=us; loop(); }
void checkPhase() {
  int on=0;
  for(int i=0;i<4;++i) { assert(simulatedPins[MOTOR_PINS[i]]==HALF_STEP[phase][i]); on+=simulatedPins[MOTOR_PINS[i]]; }
  assert(on==1 || on==2);
}
int main() {
  setup();
  for(int i=0;i<100;++i) advance(10000);
  assert(!remainingSteps && allOff()); // no automatic motion on startup
  send('?'); assert(allOff());
  send('j'); assert(remainingSteps==512);
  auto before=phase;
  advance(8000); assert(completedSteps==1 && phase==((before+1)&7)); checkPhase();
  auto count=remainingSteps;
  send('m'); assert(remainingSteps==count); // busy commands cannot overwrite motion
  send('r'); assert(direction==1);
  send('s'); assert(!remainingSteps && !settling && allOff());
  advance(100000); assert(allOff());
  send('r'); assert(direction==-1);
  before=phase; send('j'); advance(8000);
  assert(phase==((before+7)&7)); checkPhase(); send('s');
  simulatedUs=UINT32_MAX-3000ULL;
  send('m'); advance(8000); // micros wraps while moving
  assert(completedSteps==1); checkPhase();
  while(remainingSteps) { advance(8000); checkPhase(); }
  assert(completedSteps==4096 && settling && !allOff());
  advance(499000); assert(settling && !allOff());
  advance(1000); assert(!settling && allOff());
  send('t');
  while(remainingSteps) { advance(8000); checkPhase(); }
  assert(completedSteps==8192 && settling);
  send('s'); assert(!settling && allOff()); // stop also cancels settling/holding
  for(char speed: {'1','2','3'}) {
    send(speed);
    const uint32_t interval=speed=='1'?4000:speed=='2'?3000:2000;
    assert(runIntervalUs==interval && allOff());
    send('n'); assert(remainingSteps==1024);
    send(speed=='1'?'3':'1'); assert(runIntervalUs==interval);
    while(remainingSteps) {
      assert(stepIntervalUs()>=interval && stepIntervalUs()<=START_INTERVAL_US);
      advance(stepIntervalUs()); checkPhase();
    }
    assert(completedSteps==1024 && settling);
    advance(500000); assert(!settling && allOff());
  }
  send('1'); assert(runIntervalUs==4000);
  std::cout<<"PASS: idle startup, phase sequence, reversal, busy rejection, stop, "
              "micros rollover, 4096/8192 counts, settling and coil release.\n";
}
