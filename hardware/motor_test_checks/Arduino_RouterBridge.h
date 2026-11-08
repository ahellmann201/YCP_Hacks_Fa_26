#pragma once
#include <deque>
#include <string>
struct SimulatedMonitor {
  std::deque<char> input;
  std::string output;
  void begin(unsigned long) {}
  int available() { return (int)input.size(); }
  int read() { char c=input.front(); input.pop_front(); return c; }
  void println(const char* text) { output+=text; output+='\n'; }
};
extern SimulatedMonitor Monitor;
