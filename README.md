# LinkedinMechaWarrior

CLI local para ayudar a redactar y preparar posts en LinkedIn usando un navegador Chromium real con perfil persistente.

El objetivo es asistencia personal con revision humana. La herramienta no scrapea LinkedIn, no interactua con otras cuentas, no agenda publicaciones y no publica por defecto. LinkedIn puede cambiar su interfaz o limitar automatizaciones; usala con prudencia y revisa sus terminos antes de depender de ella en un flujo profesional.

## Que hace

- Genera un borrador de post desde una idea o texto base.
- Abre LinkedIn en Chromium con una sesion persistente guardada en `.browser-profile/`.
- Permite iniciar sesion desde la terminal con `auth` o `login`. La contrasena se pide con prompt seguro.
- Puede guardar la contrasena en el llavero seguro del sistema usando `keyring`, solo si lo pides con `--save-password`.
- Mantiene fallback manual para 2FA, captcha, checkpoints o cambios de UI.
- Permite consultar estado de sesion con `status`.
- Abre el compositor de LinkedIn y pega el texto para revision manual.
- Bloquea la publicacion automatica salvo que se cumplan tres condiciones:
  - `ALLOW_AUTO_PUBLISH=true`
  - flag explicito `--publish`
  - confirmacion interactiva exacta: `PUBLICAR`

## Limitaciones

- LinkedIn cambia selectores y textos de interfaz con frecuencia. Si el compositor no aparece, la herramienta guarda screenshots en `debug/`.
- El login desde CLI rellena el formulario en el navegador. LinkedIn puede requerir pasos manuales.
- La contrasena solo se guarda si usas `--save-password`, y se guarda mediante el llavero del sistema, no en `.env` ni en archivos del proyecto.
- El generador de posts es local y determinista; no llama a modelos externos.
- El modo `publish` existe solo como opcion protegida. La ruta recomendada es preparar el post y publicarlo manualmente tras revisarlo.

## Instalacion

Requisitos:

- Python 3.11+
- Playwright
- Chromium instalado por Playwright
- Un backend de llavero del sistema si quieres usar `--save-password`

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python -m playwright install chromium
cp .env.example .env
```

Si quieres generar un ejecutable compilado, instala tambien las dependencias de build:

```bash
pip install -e ".[build]"
```

## Configuracion

Edita `.env` si quieres cambiar rutas o limites:

```bash
LINKEDIN_URL=https://www.linkedin.com/feed/
BROWSER_PROFILE_DIR=.browser-profile
DEBUG_DIR=debug
HEADLESS=false
DEFAULT_TIMEOUT_MS=30000
MAX_POST_CHARS=3000
ALLOW_AUTO_PUBLISH=false
```

No pongas credenciales en `.env`. La contrasena se pide en terminal cuando ejecutas `auth` o `login`; si usas `--save-password`, se guarda con `keyring` en el llavero seguro del sistema. La sesion tambien se conserva en el perfil persistente del navegador.

## Uso

Generar un borrador:

```bash
linkedin-cli draft \
  --idea "Lo que aprendi automatizando procesos internos con IA" \
  --tone profesional \
  --length media
```

Guardar el borrador en un archivo:

```bash
linkedin-cli draft \
  --idea "Lo que aprendi automatizando procesos internos con IA" \
  --tone profesional \
  --length media \
  --output post.txt
```

Vista previa sin abrir LinkedIn:

```bash
linkedin-cli preview --text-file post.txt
```

Abrir LinkedIn con perfil persistente:

```bash
linkedin-cli open --keep-open
```

Verificar si hay sesion activa:

```bash
linkedin-cli status
```

Iniciar sesion desde la terminal:

```bash
linkedin-cli auth --email tu-email@example.com --keep-open
```

El comando pedira la contrasena con un prompt seguro:

```text
LinkedIn password:
```

Guardar la contrasena de forma segura en el llavero del sistema tras un login correcto:

```bash
linkedin-cli auth --email tu-email@example.com --save-password
```

Despues, puedes iniciar sesion usando la contrasena guardada:

```bash
linkedin-cli auth --email tu-email@example.com
```

Si omites `--email`, el CLI intenta usar la ultima cuenta guardada en el llavero:

```bash
linkedin-cli auth
```

Borrar la contrasena guardada:

```bash
linkedin-cli auth --email tu-email@example.com --forget-password
```

Tambien puedes usar el alias `login`:

```bash
linkedin-cli login --email tu-email@example.com
```

Si prefieres escribir todo directamente en el navegador o LinkedIn muestra 2FA, captcha o un checkpoint:

```bash
linkedin-cli auth --manual --keep-open
```

Preparar un post en el editor de LinkedIn:

```bash
linkedin-cli prepare-post --text-file post.txt
```

Publicacion automatica protegida:

```bash
ALLOW_AUTO_PUBLISH=true linkedin-cli prepare-post \
  --text-file post.txt \
  --publish
```

Tambien puedes ejecutar el modulo directamente si no instalas el comando:

```bash
python -m linkedin_automation.cli status
```

Aunque el flag este presente, la herramienta pedira escribir `PUBLICAR`. Si falta la variable, el flag o la confirmacion exacta, no publica.

## Tonos y longitudes

Tonos disponibles:

- `profesional`
- `tecnico` o `técnico`
- `cercano`
- `fundador`, `startup` o `fundador/startup`
- `educativo`

Longitudes disponibles:

- `corta`
- `media`
- `larga`

## Estructura

```text
linkedin_automation/
  __init__.py
  __main__.py
  browser.py
  cli.py
  config.py
  credentials.py
  linkedin.py
  post_generator.py
  utils.py
.github/
  workflows/
    release-on-push.yml
scripts/
  build_binary.py
  linkedin_cli_entry.py
tests/
  test_cli.py
  test_config.py
  test_credentials.py
  test_post_generator.py
.env.example
pyproject.toml
requirements.txt
```

## Diagnostico

Si LinkedIn cambia la interfaz, el comando `prepare-post` puede fallar con errores como:

- sesion no autenticada
- editor no encontrado
- timeout
- post demasiado largo
- llavero seguro no disponible al usar `--save-password`

Cuando hay un fallo de navegador, se intenta guardar una captura en `debug/` para revisar que estaba mostrando LinkedIn.

## Tests

```bash
pytest
```

Los tests cubren la generacion local de posts y la validacion de configuracion. No abren LinkedIn.

## Compilar

Puedes crear un ejecutable local con PyInstaller:

```bash
source .venv/bin/activate
pip install -e ".[build]"
python scripts/build_binary.py --clean
```

El binario queda en:

```bash
dist/linkedin-cli
```

Uso del binario:

```bash
./dist/linkedin-cli --help
./dist/linkedin-cli draft --idea "Lo que aprendi automatizando procesos internos con IA"
```

Notas importantes:

- El ejecutable no incluye `.env`, `.browser-profile/`, `debug/`, contrasenas ni sesiones.
- Chromium de Playwright no se empaqueta dentro del binario. Debe estar instalado en la maquina donde ejecutes comandos de navegador.
- En la maquina de build o destino, instala Chromium con:

```bash
python -m playwright install chromium
```

- Si distribuyes solo el binario a otra maquina sin Python, tendras que provisionar tambien los navegadores de Playwright o usar una instalacion local de Python para ejecutar `playwright install chromium`.
- `--save-password` sigue usando el llavero seguro del sistema de la maquina donde se ejecuta el binario.

Tambien puedes construir en modo carpeta, mas facil de inspeccionar y depurar:

```bash
python scripts/build_binary.py --onedir --clean
```

## Releases Automaticos

El repositorio incluye un workflow de GitHub Actions en `.github/workflows/release-on-push.yml`.

Cada `push` a una rama compila todos los commits incluidos en ese push y crea un release versionado por commit con tag:

```text
v<version-pyproject>-build.<github-run-number>.<commit-index>
```

Ejemplo:

```text
v0.1.0-build.12.1
```

Cada release incluye dos assets directos, sin `.zip` ni `.tar.gz` propios:

- Linux x86_64: `linkedin-cli-linux`
- Windows x86_64: `linkedin-cli.exe`

El workflow:

- ejecuta tests antes de empaquetar
- compila con PyInstaller en `ubuntu-latest` y `windows-latest`
- sube solo los binarios compilados como assets del release
- actualiza el release si se re-ejecuta para el mismo commit

GitHub siempre anade automaticamente los assets `Source code (zip)` y `Source code (tar.gz)` a cualquier release. No forman parte del empaquetado de la aplicacion.

Para que pueda crear releases, el workflow usa:

```yaml
permissions:
  contents: write
```
