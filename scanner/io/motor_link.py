"""Send one command to the UNO Q motor sketch when a serial port is configured."""
import os
import time

COMMANDS = set("jmtnsr123?")


def configured_port():
    return os.getenv("SCANNER_MOTOR_PORT", "").strip()


def send_command(command, wait_done=False, timeout=20):
    command = str(command or "")
    if len(command) != 1 or command.lower() not in COMMANDS:
        raise ValueError("Unknown motor command.")
    port = configured_port()
    if not port:
        return {"connected": False, "detail": "Set SCANNER_MOTOR_PORT to the Arduino port."}
    import serial
    with serial.Serial(port, 115200, timeout=0.2) as link:
        time.sleep(0.2)
        link.reset_input_buffer()
        link.write(command.encode("ascii"))
        if not wait_done:
            return {"connected": True, "sent": command}
        deadline = time.time() + timeout
        text = ""
        while time.time() < deadline:
            chunk = link.read(256)
            if not chunk:
                time.sleep(0.05)
                continue
            text += chunk.decode("utf-8", "replace")
            if "DONE:" in text or "STOPPED:" in text:
                return {"connected": True, "sent": command, "reply": text.strip()[-400:]}
        return {"connected": True, "sent": command, "reply": text.strip()[-400:], "timed_out": True}
