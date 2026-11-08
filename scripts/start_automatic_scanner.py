"""Start the scanner locally with a persistent, generated clerk password."""
import json
import os
from pathlib import Path
import secrets
import sys

root=Path(__file__).resolve().parents[1]
os.chdir(root);sys.path.insert(0,str(root))
config=root/'.env.automatic-scanner'
if config.exists(): settings=json.loads(config.read_text())
else:
    settings={'username':'clerk','password':secrets.token_urlsafe(18),'local_url':'http://127.0.0.1:8000'}
    config.write_text(json.dumps(settings,indent=2),encoding='utf-8')
os.environ.setdefault('SCANNER_ACCESS_PASSWORD',settings['password'])
os.environ.setdefault('SCANNER_MOTOR_URL','http://127.0.0.1:8765')
os.environ.setdefault('SCANNER_OCR_THREADS','3')

if __name__=='__main__':
    import uvicorn
    tls=root/'.env.local-https'
    options={}
    if (tls/'config.json').exists():
        network=json.loads((tls/'config.json').read_text())
        host,port=network['ip'],network['port']
        options={'ssl_keyfile':str(tls/'server.key.pem'),'ssl_certfile':str(tls/'server.pem')}
        print(f'Local scanner: https://{host}:{port}',flush=True)
    else:
        host,port='127.0.0.1',8000
        print('Local scanner: http://127.0.0.1:8000',flush=True)
    print('Login is saved locally in .env.automatic-scanner (excluded from Git).',flush=True)
    uvicorn.run('main:app',host=host,port=port,proxy_headers=True,forwarded_allow_ips='127.0.0.1',**options)
