# Let's Encrypt certificates using Dinahosting DNS

[Español](README.md)

This hook uses the Dinahosting API for Certbot's DNS-01 challenge. It issues a certificate for `*.example.com` and keeps it in Certbot's local directory. Optionally, it sends `fullchain.pem` and `privkey.pem` to an **FTPS server (explicit TLS)**. The zone apex `example.com` is not covered.

You need Linux, Python 3.9+, Certbot, and Dinahosting API access to edit the public DNS zone. Certbot generates the certificate on the machine running this hook, not at Dinahosting.

## Setup

Run these steps on the machine where you will use Certbot:

1. From the project root, install the hook and configuration:

   ```bash
   sudo install -d -m 700 /etc/dinahosting-acme
   sudo install -m 700 dns_hook.py /etc/dinahosting-acme/dns_hook.py
   sudo install -m 600 examples/config.example.json /etc/dinahosting-acme/config.json
   sudoedit /etc/dinahosting-acme/config.json
   ```

2. Edit `config.json`: set `zone`, API credentials, and `cert_name`. Use `example.com` for `zone`, without `*.`. Keep the file owned by root with mode `600`; do not commit it. Increase `propagation_seconds` if DNS updates take longer. To send files by FTPS as well, add these fields to the same JSON (with a comma after `cert_name`):

   ```json
   "ftps_host": "ftp.example.com",
   "ftps_port": 21,
   "ftps_user": "FTPS_USER",
   "ftps_password": "FTPS_PASSWORD",
   "ftps_directory": "/certificates/example.com"
   ```

   The remote directory must already exist and restrict access to the private key. Without `ftps_host`, files stay local.

3. Test DNS-01 with Let's Encrypt staging. Replace the domain, email, and certificate name with your values:

   ```bash
   sudo certbot certonly --manual --preferred-challenges dns \
     --manual-auth-hook '/etc/dinahosting-acme/dns_hook.py auth' \
     --manual-cleanup-hook '/etc/dinahosting-acme/dns_hook.py cleanup' \
     --deploy-hook '/etc/dinahosting-acme/dns_hook.py deploy' \
     --non-interactive --agree-tos --email admin@example.com \
     --cert-name example-wildcard -d '*.example.com' --dry-run
   ```

4. If staging succeeds, repeat the command **without `--dry-run`**. Check `sudo certbot certificates` and `/etc/letsencrypt/live/example-wildcard/` for `fullchain.pem` and `privkey.pem`. If you configured FTPS, confirm that both files arrived there too. Dry runs do not upload files.

5. Test renewal: `sudo certbot renew --cert-name example-wildcard --dry-run`.

6. Schedule renewal. Check for a built-in Certbot timer with `systemctl list-timers --all | grep -i certbot`. If none exists, find Certbot with `command -v certbot`, run `sudo crontab -e`, and add this line using the actual path:

   ```cron
   17 4 * * * /usr/bin/certbot renew --cert-name example-wildcard -q
   ```

Certbot renews only when due. If FTPS is configured, it uploads after successful issuance or renewal. Monitor Certbot errors and, if using FTPS, the certificate date at the destination: a failed upload does not necessarily mark the renewal as failed. Keep the script and config at the same paths.

The API supports deleting one TXT value, so cleanup preserves other TXT values at the same name. This setup supports **one wildcard per certificate**. It has not been tested here with live Dinahosting credentials or an FTPS server.

Local tests: `python3 -m unittest discover -s tests -v`.

References: [Dinahosting API](https://dinahosting.com/api/) · [Certbot hooks and renewal](https://eff-certbot.readthedocs.io/en/stable/using.html).

MIT license: [LICENSE](LICENSE).
