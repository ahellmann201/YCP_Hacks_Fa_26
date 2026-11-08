#pragma once
#include <cstdint>
constexpr int LOW=0, HIGH=1, OUTPUT=1;
extern uint64_t simulatedUs;
extern int simulatedPins[32];
inline uint32_t micros() { return (uint32_t)simulatedUs; }
inline uint32_t millis() { return (uint32_t)(simulatedUs/1000); }
inline void pinMode(uint8_t, int) {}
inline void digitalWrite(uint8_t pin, int value) { simulatedPins[pin]=value; }
