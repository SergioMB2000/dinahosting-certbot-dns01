# Certificados Let's Encrypt con DNS de Dinahosting

[English](README.en.md)

Este hook usa la API de Dinahosting para superar el desafío DNS-01 de Certbot. Emite un certificado para `*.example.com` y lo deja en la ruta local de Certbot. Opcionalmente envía `fullchain.pem` y `privkey.pem` a un servidor **FTPS (FTP con TLS explícito)**. El dominio raíz `example.com` no queda cubierto.

Necesitas Linux, Python 3.9+, Certbot y acceso a la API de Dinahosting con permiso para editar la zona DNS pública. El certificado se genera en el equipo que ejecuta Certbot, no en Dinahosting.

## Puesta en marcha

Ejecuta estos pasos en el equipo donde usarás Certbot:

1. Copia el hook y su configuración desde la raíz del proyecto:

   ```bash
   sudo install -d -m 700 /etc/dinahosting-acme
   sudo install -m 700 dns_hook.py /etc/dinahosting-acme/dns_hook.py
   sudo install -m 600 examples/config.example.json /etc/dinahosting-acme/config.json
   sudoedit /etc/dinahosting-acme/config.json
   ```

2. En `config.json`, cambia `zone`, usuario y contraseña de la API y `cert_name`. `zone` es `example.com`, sin `*.`. El archivo debe ser de `root` y tener permisos `600`; no lo subas a Git. `propagation_seconds` indica cuánto espera Certbot tras crear el TXT; súbelo si el DNS tarda en propagarse. Para enviar también por FTPS, añade estos campos dentro del mismo JSON (con una coma después de `cert_name`):

   ```json
   "ftps_host": "ftp.example.com",
   "ftps_port": 21,
   "ftps_user": "FTPS_USER",
   "ftps_password": "FTPS_PASSWORD",
   "ftps_directory": "/certificates/example.com"
   ```

   El directorio remoto debe existir y limitar el acceso a la clave privada. Si no configuras `ftps_host`, todo queda en local.

3. Prueba DNS-01 con el entorno de pruebas de Let's Encrypt. Cambia dominio, correo y nombre del certificado por los de `config.json`:

   ```bash
   sudo certbot certonly --manual --preferred-challenges dns \
     --manual-auth-hook '/etc/dinahosting-acme/dns_hook.py auth' \
     --manual-cleanup-hook '/etc/dinahosting-acme/dns_hook.py cleanup' \
     --deploy-hook '/etc/dinahosting-acme/dns_hook.py deploy' \
     --non-interactive --agree-tos --email admin@example.com \
     --cert-name example-wildcard -d '*.example.com' --dry-run
   ```

4. Si la prueba termina bien, repite el comando **sin `--dry-run`** para emitir el certificado real. Comprueba con `sudo certbot certificates` que existe `/etc/letsencrypt/live/example-wildcard/`, con `fullchain.pem` y `privkey.pem`. Si configuraste FTPS, comprueba que llegaron también al servidor. La prueba con `--dry-run` no ejecuta el envío FTPS.

5. Prueba la renovación:

   ```bash
   sudo certbot renew --cert-name example-wildcard --dry-run
   ```

6. Programa la renovación. Comprueba primero si tu instalación ya trae un temporizador de Certbot con `systemctl list-timers --all | grep -i certbot`. Si no lo hay, consulta la ruta con `command -v certbot`, abre `sudo crontab -e` y añade, usando esa ruta:

   ```cron
   17 4 * * * /usr/bin/certbot renew --cert-name example-wildcard -q
   ```

Certbot solo renueva cuando corresponde. Si configuraste FTPS, ejecuta el envío tras una emisión o renovación correcta. Vigila los errores de Certbot y, si usas FTPS, la fecha del certificado en el destino: un fallo del envío no convierte necesariamente la renovación en fallida. Mantén el mismo script y `config.json` en esas rutas.

La API permite borrar un TXT por su valor, por lo que el hook no elimina otros TXT del mismo nombre. Está preparado para **un solo wildcard por certificado**. No se ha probado aquí con credenciales reales de Dinahosting ni con un servidor FTPS real.

Pruebas locales: `python3 -m unittest discover -s tests -v`.

Referencias: [API de Dinahosting](https://dinahosting.com/api/) · [Certbot: hooks y renovación](https://eff-certbot.readthedocs.io/en/stable/using.html).

Licencia MIT: [LICENSE](LICENSE).
