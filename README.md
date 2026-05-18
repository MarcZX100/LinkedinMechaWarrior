# LinkedinMechaWarrior

CLI local para ayudar a redactar y preparar posts en LinkedIn usando un navegador Chromium real con perfil persistente.

El objetivo es asistencia personal con revision humana. La herramienta no scrapea LinkedIn, no interactua con otras cuentas, no agenda publicaciones y no publica por defecto. LinkedIn puede cambiar su interfaz o limitar automatizaciones; usala con prudencia y revisa sus terminos antes de depender de ella en un flujo profesional.

## Que hace

- Genera un borrador de post desde una idea o texto base.
- Abre LinkedIn en Chromium con una sesion persistente guardada en `.browser-profile/`.
- Permite iniciar sesion desde la terminal con `auth` o `login`. La contrasena se pide con prompt seguro y no se guarda.
- Mantiene fallback manual para 2FA, captcha, checkpoints o cambios de UI.
- Permite consultar estado de sesion con `status`.
- Abre el compositor de LinkedIn y pega el texto para revision manual.
- Bloquea la publicacion automatica salvo que se cumplan tres condiciones:
  - `ALLOW_AUTO_PUBLISH=true`
  - flag explicito `--publish`
  - confirmacion interactiva exacta: `PUBLICAR`

## Limitaciones

- LinkedIn cambia selectores y textos de interfaz con frecuencia. Si el compositor no aparece, la herramienta guarda screenshots en `debug/`.
- El login desde CLI rellena el formulario en el navegador, pero no guarda credenciales. LinkedIn puede requerir pasos manuales.
- El generador de posts es local y determinista; no llama a modelos externos.
- El modo `publish` existe solo como opcion protegida. La ruta recomendada es preparar el post y publicarlo manualmente tras revisarlo.

## Instalacion

Requisitos:

- Python 3.11+
- Playwright
- Chromium instalado por Playwright

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
python -m playwright install chromium
cp .env.example .env
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

No pongas credenciales en `.env`. La contrasena se pide en terminal cuando ejecutas `auth` o `login`, y la sesion se conserva en el perfil persistente del navegador.

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
LinkedIn password (not stored):
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
  browser.py
  cli.py
  config.py
  linkedin.py
  post_generator.py
  utils.py
tests/
  test_cli.py
  test_config.py
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

Cuando hay un fallo de navegador, se intenta guardar una captura en `debug/` para revisar que estaba mostrando LinkedIn.

## Tests

```bash
pytest
```

Los tests cubren la generacion local de posts y la validacion de configuracion. No abren LinkedIn.
