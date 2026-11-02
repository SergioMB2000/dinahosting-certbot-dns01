"""Offline checks: python3 -m unittest discover -s tests -v"""

import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

spec = importlib.util.spec_from_file_location('dns_hook', Path(__file__).resolve().parents[1] / 'dns_hook.py')
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class Response:
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self): return json.dumps({'responseCode': 1000}).encode()


class HookTests(unittest.TestCase):
    def test_local_deploy_does_not_connect(self):
        with patch.object(hook.ftplib, 'FTP_TLS') as factory:
            hook.deploy({'cert_name': 'example-wildcard'})
            factory.assert_not_called()

    def test_dns_add_and_exact_cleanup(self):
        settings = {'zone': 'example.com', 'username': 'user', 'password': 'pass', 'propagation_seconds': 0}
        env = {'CERTBOT_DOMAIN': '*.example.com', 'CERTBOT_VALIDATION': 'tokenABC'}
        with patch.dict(os.environ, env, clear=True), patch.object(hook.time, 'sleep') as sleep:
            for command, field in [('Domain_Zone_AddTypeTXT', 'text'), ('Domain_Zone_DeleteTypeTXT', 'value')]:
                with self.subTest(command=command), patch.object(hook.urllib.request, 'urlopen', return_value=Response()) as call:
                    hook.dns(command, settings)
                    request = call.call_args.args[0]
                    params = parse_qs(request.data.decode())
                    self.assertEqual(request.method, 'POST')
                    self.assertEqual(params['domain'], ['example.com'])
                    self.assertEqual(params['hostname'], ['_acme-challenge'])
                    self.assertEqual(params[field], ['tokenABC'])
                    self.assertNotIn('AUTH_PWD', params)
        sleep.assert_called_once_with(0)

    def test_rejects_wrong_domain_before_api_call(self):
        with patch.dict(os.environ, {'CERTBOT_DOMAIN': '*.other.com', 'CERTBOT_VALIDATION': 'abc'}, clear=True):
            with patch.object(hook.urllib.request, 'urlopen') as call:
                with self.assertRaises(ValueError):
                    hook.dns('Domain_Zone_AddTypeTXT', {'zone': 'example.com'})
                call.assert_not_called()

    def test_deploy_uses_ftps_for_both_files(self):
        lineage = Path('/etc/letsencrypt/live/example-wildcard')
        settings = {'cert_name': 'example-wildcard', 'ftps_host': 'ftp.example.com',
                    'ftps_user': 'u', 'ftps_password': 'p', 'ftps_directory': '/certs'}
        contents = {'privkey.pem': b'key', 'fullchain.pem': b'certificate'}
        uploaded = {}
        with patch.dict(os.environ, {'RENEWED_LINEAGE': str(lineage)}, clear=True):
            with patch.object(hook.Path, 'open', autospec=True,
                              side_effect=lambda path, mode: io.BytesIO(contents[path.name])):
                with patch.object(hook.ftplib, 'FTP_TLS') as factory:
                    ftp = factory.return_value.__enter__.return_value
                    ftp.storbinary.side_effect = lambda command, source: uploaded.update({command: source.read()})
                    hook.deploy(settings)
                    ftp.connect.assert_called_once_with('ftp.example.com', 21, timeout=45)
                    ftp.prot_p.assert_called_once_with()
                    ftp.cwd.assert_called_once_with('/certs')
        self.assertEqual(uploaded, {'STOR privkey.pem': b'key', 'STOR fullchain.pem': b'certificate'})


if __name__ == '__main__':
    unittest.main()
