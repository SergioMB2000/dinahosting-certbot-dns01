#!/usr/bin/env python3
"""Certbot DNS-01 and FTPS deploy hooks for one Dinahosting wildcard."""

import base64
import ftplib
import json
import os
from pathlib import Path
import ssl
import sys
import time
import urllib.parse
import urllib.request

CONFIG_FILE = Path('/etc/dinahosting-acme/config.json')
API_URL = 'https://dinahosting.com/special/api.php'


def config():
    path = Path(os.environ.get('DINAHOSTING_CONFIG_FILE', CONFIG_FILE))
    if path.stat().st_mode & 0o077:
        raise PermissionError('Config file must have mode 600')
    return json.loads(path.read_text(encoding='utf-8'))


def dns(command, settings):
    zone = settings['zone'].lower().rstrip('.')
    if '*' in zone or '.' not in zone:
        raise ValueError('Invalid DNS zone')
    if os.environ.get('CERTBOT_DOMAIN', '').lower().rstrip('.') != '*.' + zone:
        raise ValueError('CERTBOT_DOMAIN must match the configured wildcard zone')
    token = os.environ.get('CERTBOT_VALIDATION', '')
    if not token or not all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in token):
        raise ValueError('Missing or invalid CERTBOT_VALIDATION')
    seconds = int(settings.get('propagation_seconds', 360))
    if not 0 <= seconds <= 3600:
        raise ValueError('propagation_seconds must be between 0 and 3600')
    params = {'command': command, 'domain': zone, 'hostname': '_acme-challenge',
              'responseType': 'Json'}
    params['text' if command == 'Domain_Zone_AddTypeTXT' else 'value'] = token
    auth = base64.b64encode((settings['username'] + ':' + settings['password']).encode()).decode()
    request = urllib.request.Request(
        API_URL, data=urllib.parse.urlencode(params).encode(),
        headers={'Authorization': 'Basic ' + auth}, method='POST')
    with urllib.request.urlopen(request, timeout=45) as response:
        result = json.load(response)
    if str(result.get('responseCode')) != '1000':
        raise RuntimeError('Dinahosting API error: %s' % result.get('responseCode', 'missing'))
    if command == 'Domain_Zone_AddTypeTXT':
        time.sleep(seconds)


def deploy(settings):
    if not settings.get('ftps_host'):
        return  # Certbot already keeps the certificate in /etc/letsencrypt/live.
    lineage = Path(os.environ['RENEWED_LINEAGE'])
    if lineage.name != settings['cert_name']:
        raise ValueError('Unexpected certificate lineage')
    with ftplib.FTP_TLS(context=ssl.create_default_context()) as ftp:
        ftp.connect(settings['ftps_host'], int(settings.get('ftps_port', 21)), timeout=45)
        ftp.login(settings['ftps_user'], settings['ftps_password'])
        ftp.prot_p()
        ftp.cwd(settings['ftps_directory'])
        for name in ('privkey.pem', 'fullchain.pem'):
            with (lineage / name).open('rb') as source:
                ftp.storbinary('STOR ' + name, source)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('auth', 'cleanup', 'deploy'):
        raise ValueError('Usage: dns_hook.py auth|cleanup|deploy')
    settings = config()
    if sys.argv[1] == 'deploy':
        deploy(settings)
    else:
        command = ('Domain_Zone_AddTypeTXT' if sys.argv[1] == 'auth'
                   else 'Domain_Zone_DeleteTypeTXT')
        dns(command, settings)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # API, FTP and JSON errors can include account details: print only their type.
        message = str(exc) if isinstance(exc, (ValueError, PermissionError, RuntimeError)) else type(exc).__name__
        print('Hook failed: ' + message, file=sys.stderr)
        sys.exit(1)
