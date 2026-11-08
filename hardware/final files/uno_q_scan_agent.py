"""Run on UNO Q Linux. Expose MCU RPC only on loopback; access via adb forward.

No CORS support. A custom header prevents browser form requests to this port.
The laptop scanner owns authentication; this service is not a public LAN API.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4


class MotorAgent:
    def __init__(self, bridge):
        self.bridge=bridge
        self.boot=uuid4().hex
        self.lock=threading.Lock()
        self.requests={}

    def status(self):
        state=json.loads(self.bridge.call('scanner_status',timeout=1))
        if state.get('protocol')!=1:
            raise ValueError('Upload motor_scan.ino first.')
        return {**state,'boot':self.boot}

    def move(self, request_id, speed):
        if not isinstance(request_id,str) or not 1<=len(request_id)<=80 or type(speed)!=int or speed not in (1,2,3):
            raise ValueError('Invalid movement request.')
        with self.lock:
            if request_id in self.requests:
                old=self.requests[request_id]
                if old['speed']!=speed: raise ValueError('Request was already used at another speed.')
                return dict(old)
            state=self.status()
            if state['state'] in (1,2): raise ValueError('Motor is busy.')
            if len(self.requests)>=4096: raise ValueError('Restart agent between scans to clear request history.')
            command_id=state['id']+1
            # Record before calling: a lost RPC response must never repeat movement.
            result={'command_id':command_id,'boot':self.boot,'speed':speed}
            self.requests[request_id]=result
            accepted=self.bridge.call('scanner_move',command_id,speed,timeout=1)
            if accepted!=1: raise ValueError('Motor rejected movement.')
            return dict(result)

    def stop(self):
        self.bridge.call('scanner_stop',timeout=1)
        return {'stopped':True,'boot':self.boot}


def handler_for(agent):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def respond(self,code,data):
            raw=json.dumps(data).encode()
            self.send_response(code); self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def handle_request(self):
            if self.headers.get('X-Scanner-Motor')!='1' or self.headers.get('Origin'):
                self.respond(403,{'detail':'Use the laptop scanner connection.'}); return
            try:
                if self.command=='GET' and self.path=='/status': result=agent.status()
                elif self.command=='POST':
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<=length<=1024: raise ValueError('Request too large.')
                    data=json.loads(self.rfile.read(length) or b'{}')
                    if self.path=='/move': result=agent.move(data.get('request_id'),data.get('speed',1))
                    elif self.path=='/stop': result=agent.stop()
                    else: self.respond(404,{'detail':'Not found'}); return
                else: self.respond(404,{'detail':'Not found'}); return
                self.respond(200,result)
            except Exception:
                self.respond(503,{'detail':'Motor bridge unavailable or command rejected. Check sketch and USB connection.'})
        do_GET=handle_request
        do_POST=handle_request
    return Handler


if __name__=='__main__':
    try:
        from arduino.router_bridge import Bridge
        bridge=Bridge()
        if not bridge.connect(timeout=5): raise SystemExit('Cannot connect to Arduino Router.')
    except ModuleNotFoundError:
        # App Lab 0.5.0 supplies this older API in its existing Python image.
        from arduino.app_utils import Bridge as bridge
    agent=MotorAgent(bridge)
    agent.status() # Fail before starting the server if the correct sketch is absent.
    try: ThreadingHTTPServer(('127.0.0.1',8765),handler_for(agent)).serve_forever()
    finally:
        try: agent.stop()
        finally:
            if hasattr(bridge,'disconnect'): bridge.disconnect()
