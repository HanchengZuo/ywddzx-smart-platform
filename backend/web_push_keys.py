"""Generate a persistent VAPID identity into a new owner-only file, never stdout."""
import argparse
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from web_push import b64, configuration


def main():
    parser=argparse.ArgumentParser(description='Generate Web Push VAPID settings; existing files are never overwritten.')
    parser.add_argument('--output',required=True)
    parser.add_argument('--subject',required=True,help='mailto:admin@example.com or public HTTPS origin')
    args=parser.parse_args()
    key=ec.generate_private_key(ec.SECP256R1())
    private=b64(key.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    if not configuration({'WEB_PUSH_VAPID_PRIVATE_KEY':private,'WEB_PUSH_SUBJECT':args.subject})['ready']:
        parser.error('A valid mailto contact or public HTTPS origin is required.')
    fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:
        output.write(f'WEB_PUSH_ENABLED=true\nWEB_PUSH_VAPID_PRIVATE_KEY={private}\nWEB_PUSH_SUBJECT={args.subject}\n')
    print('VAPID settings saved to the requested 0600 file. Keep it private and persistent; no keys printed.')


if __name__=='__main__': main()
