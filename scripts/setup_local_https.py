"""Create a private local CA, a server certificate and an iPhone root-only profile."""
from datetime import datetime, timedelta, timezone
import ipaddress
import json
from pathlib import Path
import plistlib
import sys
from uuid import uuid4
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

root=Path(__file__).resolve().parents[1]
ip=ipaddress.ip_address(sys.argv[1])
private=root/'.env.local-https'; private.mkdir(exist_ok=True)
public=root/'tmp'/'iphone-https-public';public.mkdir(parents=True,exist_ok=True)
now=datetime.now(timezone.utc)
ca_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Three Tube Scanner Local CA')])
key_path=private/'ca.key.pem';cert_path=private/'ca.pem'
if key_path.exists() and cert_path.exists():
    ca_key=serialization.load_pem_private_key(key_path.read_bytes(),password=None)
    ca=x509.load_pem_x509_certificate(cert_path.read_bytes())
else:
    ca_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    ca=(x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=90))
        .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
        .add_extension(x509.KeyUsage(False,False,False,False,False,True,True,False,False),critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),critical=False).sign(ca_key,hashes.SHA256()))
    key_path.write_bytes(ca_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    cert_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
server_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
server=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,str(ip))]))
    .issuer_name(ca.subject).public_key(server_key.public_key()).serial_number(x509.random_serial_number())
    .not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=30))
    .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
    .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ip),x509.IPAddress(ipaddress.ip_address('127.0.0.1')),x509.DNSName('localhost')]),critical=False)
    .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
    .add_extension(x509.KeyUsage(True,False,True,False,False,False,False,False,False),critical=True)
    .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False).sign(ca_key,hashes.SHA256()))
(private/'server.key.pem').write_bytes(server_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
(private/'server.pem').write_bytes(server.public_bytes(serialization.Encoding.PEM)+ca.public_bytes(serialization.Encoding.PEM))
(private/'config.json').write_text(json.dumps({'ip':str(ip),'port':8443}))
profile={'PayloadType':'Configuration','PayloadVersion':1,'PayloadIdentifier':'local.three-tube-scanner',
 'PayloadUUID':str(uuid4()),'PayloadDisplayName':'Three Tube Scanner — local HTTPS',
 'PayloadDescription':'Installs only the local scanner certificate. No device management or VPN.',
 'PayloadContent':[{'PayloadType':'com.apple.security.root','PayloadVersion':1,
 'PayloadIdentifier':'local.three-tube-scanner.ca','PayloadUUID':str(uuid4()),
 'PayloadDisplayName':'Three Tube Scanner Local CA','PayloadCertificateFileName':'scanner-root.cer',
 'PayloadContent':ca.public_bytes(serialization.Encoding.DER)}]}
(public/'scanner.mobileconfig').write_bytes(plistlib.dumps(profile))
(public/'index.html').write_text(f'''<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Local scanner setup</title>
<body style="font:18px system-ui;max-width:600px;margin:30px auto;padding:20px"><h1>Local scanner setup</h1>
<ol><li><a href="/scanner.mobileconfig">Download the scanner certificate profile</a>.</li>
<li>Open iPhone Settings → Profile Downloaded → Install.</li>
<li>Settings → General → About → Certificate Trust Settings: enable Three Tube Scanner Local CA.</li>
<li><a href="https://{ip}:8443">Open the secure scanner</a> and sign in with the clerk login saved on the laptop.</li></ol>
<p>Stay on the same Wi-Fi as the laptop. Keep the phone in landscape with one tube in each third of the image.</p>
<p>This profile adds only a local certificate. Remove it after the demo through Settings → General → VPN &amp; Device Management.</p></body></html>''',encoding='utf-8')
print(f'Certificate setup: http://{ip}:8081')
print(f'Scanner: https://{ip}:8443')
print('CA SHA256:',ca.fingerprint(hashes.SHA256()).hex())
