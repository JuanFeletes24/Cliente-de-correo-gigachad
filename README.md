# Redes de Computadores - Proyecto #1: Cliente de Correo Electrónico

Aplicación de escritorio desarrollada en Python con **Flet**, que implementa un cliente de correo electrónico completo con soporte para protocolos **IMAP**, **POP3** y **SMTP**, almacenamiento local en base de datos **SQLite** para lectura offline y **cifrado simétrico de mensajes por contacto**.

---

## 👥 Integrantes
* **Sebastián Pérez**
* **Juan Daniel Moreno**
* **Juan Felipe Rojas**

---

## 📋 Mapeo de Requerimientos y Arquitectura de Código

A continuación se detalla cómo y en qué archivos/módulos se da cumplimiento a cada uno de los requerimientos especificados en el documento del proyecto:

| # | Requerimiento | Descripción | Implementación en Código |
|---|---|---|---|
| **1** | **Listado de últimos mensajes** | Espacio en la interfaz que lista los correos recibidos en las últimas dos semanas (o período configurable). | **`src/modules/email.py`**:<br>• `ImapEmail.get_emails()`: Realiza búsqueda IMAP usando `SINCE` calculando los últimos $N$ días.<br>• `PopEmail.get_mails()`: Descarga los encabezados y filtra por fecha localmente.<br>**`src/main.py`**:<br>• `load_emails_from_db()` y `email_card()` muestran el listado en la columna izquierda. |
| **2** | **Cuerpo del correo** | Al hacer clic en un correo de la lista, se carga su contenido en el panel derecho. | **`src/main.py`**:<br>• `show_body()`: Maneja el clic en la tarjeta del correo, parsea y limpia el contenido HTML usando `BeautifulSoup` y lo muestra formateado en `ft.Markdown`.<br>• `open_in_browser()`: Botón para visualizar el HTML original completo en el navegador web nativo. |
| **3** | **Configuración** | Formulario para configurar usuario, contraseña de aplicación, proveedor/servidor y puerto. | **`src/main.py`** & **`src/modules/email_config.ini`**:<br>• `open_settings()`: Modal con campos para usuario, contraseña, servidores y puertos (IMAP: 993, POP: 995, SMTP: 465).<br>• `update_config_file()`: Persiste la configuración en el archivo `.ini`. |
| **4** | **Backup (Modo Offline)** | Los mensajes deben descargarse en una base de datos local para recuperarlos sin acceso a Internet. | **`src/modules/db.py`**:<br>• Base de datos SQLite (`local_mail.db`).<br>• `save_email()`: Guarda cada correo (`uid`, `account`, `sender`, `subject`, `date`, `body`).<br>• `get_all_emails()`: Permite leer y consultar todos los correos guardados de forma local sin requerir conexión. |
| **5** | **Configuración (Protocolo y Período)** | Formulario que permite alternar el protocolo de manipulación (POP / IMAP) y los días de descarga. | **`src/main.py`**:<br>• Diálogo de configuración con selector desplegable (`ft.Dropdown`) para elegir entre `imap` y `pop`, y campo numérico para definir el período de días a descargar (por defecto 14 días / 2 semanas). |
| **6** | **Encriptación** | El mensaje se envía cifrado al servidor de correo (SMTP) y se descifra en el cliente del receptor. | **`src/modules/crypto.py`**:<br>• `encrypt_message()` y `decrypt_message()` utilizando cifrado simétrico robusto (**Fernet / AES** con derivación SHA-256).<br>**`src/modules/db.py`**:<br>• `save_contact_key()` y `get_contact_key()`: Almacena claves secretas individuales por cada contacto/correo.<br>**`src/modules/email.py`**:<br>• `SmtpSender.send_email()`: Cifra el cuerpo del correo antes de enviarlo por SMTP si el destinatario tiene clave configurada.<br>• `_save_to_db()`: Descifra automáticamente el correo entrante si coincide con la clave registrada del remitente. |

---

## 🛠️ Estructura del Proyecto

```text
email_gui/
├── pyproject.toml               # Configuración de dependencias del proyecto
├── README.md                    # Documentación técnica y guía de uso
├── .gitignore                   # Archivos ignorados por control de versiones
└── src/
    ├── main.py                  # Interfaz gráfica de usuario (Flet 0.86)
    └── modules/
        ├── crypto.py            # Módulo de cifrado y descifrado simétrico (Fernet)
        ├── db.py                # Gestor de base de datos local SQLite (Offline backup)
        ├── email.py             # Clases de manipulación de correo (ImapEmail, PopEmail, SmtpSender)
        └── email_config.ini     # Archivo de persistencia de configuración del cliente
```

---

## ⚙️ Guía de Uso de la Aplicación

1. **Configuración de Cuenta (⚙️):**
   * Haz clic en el icono de engranaje en la barra superior.
   * Ingresa tu correo electrónico y tu **Contraseña de Aplicación** (para cuentas de Gmail u Outlook).
   * Selecciona el protocolo deseado (`imap` o `pop`) y define el período de descarga (14 días por defecto).
   * Guarda los cambios.

2. **Gestión de Claves de Cifrado (🔒):**
   * Haz clic en el icono de candado en la barra superior.
   * Ingresa el correo de tu contacto y asigna una clave secreta compartida.
   * Haz clic en **Guardar Clave**.

3. **Sincronización (🔄):**
   * Presiona el botón de refrescar para descargar los correos según el protocolo seleccionado.
   * Los correos descargados quedarán respaldados automáticamente en la base de datos SQLite para consulta sin conexión.

4. **Redactar y Enviar Correos (+):**
   * Haz clic en el botón flotante inferior derecho **Redactar**.
   * Si el destinatario tiene una clave configurada en la sección de claves, el mensaje se enviará cifrado al servidor.

---
## 💻 Entorno y Ejecución

El proyecto utiliza `pyproject.toml` para definir sus dependencias y configuración. Se recomienda utilizar **uv** para crear y gestionar automáticamente el entorno virtual.

### Preparar el entorno

Desde la raíz del proyecto:

```bash
uv sync
```

Este comando:

* crea automáticamente el entorno virtual `.venv`;
* instala las dependencias definidas en `pyproject.toml`;
* mantiene sincronizado el entorno del proyecto.

### Ejecutar la aplicación

```bash
uv run python src/main.py
```

También puede ejecutarse directamente mediante Flet:

```bash
uv run flet run
```

> [!NOTE]
> No es necesario instalar manualmente `flet`, `cryptography`, `beautifulsoup4` o `markdownify`, ya que estas dependencias están declaradas en `pyproject.toml` y son instaladas automáticamente por `uv sync`.

### Ejecutar la aplicación

#### Escritorio
Ejecutar como aplicación de escritorio:

```bash
python src/main.py
```
*(o también: `flet run`)*

#### Web

```bash
flet run --web
```

Para más detalles sobre cómo ejecutar la aplicación, consulta la [Guía de inicio rápido de Flet](https://flet.dev/docs/).

> [!NOTE]
> En Gmail se debe generar una contraseña de aplicación y configurarla desde el menú de la aplicación (⚙️) o editando el archivo `./src/modules/email_config.ini` reemplazando el parámetro `password` por el generado.

---

## 📦 Construir y Empaquetar la Aplicación

### Android

```bash
flet build apk -v
```
Para más detalles sobre cómo compilar y firmar `.apk` o `.aab`, consulta la [Guía de empaquetado para Android](https://flet.dev/docs/publish/android/).

### iOS

```bash
flet build ipa -v
```
Para más detalles sobre cómo compilar y firmar `.ipa`, consulta la [Guía de empaquetado para iOS](https://flet.dev/docs/publish/ios/).

### macOS

```bash
flet build macos -v
```
Para más detalles sobre cómo crear el paquete para macOS, consulta la [Guía de empaquetado para macOS](https://flet.dev/docs/publish/macos/).

### Linux

```bash
flet build linux -v
```
Para más detalles sobre cómo crear el paquete para Linux, consulta la [Guía de empaquetado para Linux](https://flet.dev/docs/publish/linux/).

### Windows

```bash
flet build windows -v
```

> [!TIP]
> Una vez finalizada la compilación, encontrarás el archivo ejecutable (`.exe`) dentro de la carpeta `build/windows`. Recuerda que para compartir la aplicación, debes copiar la carpeta `windows` completa, no solo el ejecutable.

Para más detalles sobre cómo crear el paquete para Windows, consulta la [Guía de empaquetado para Windows](https://flet.dev/docs/publish/windows/).

### Web

```bash
flet build web -v
```
Para más detalles sobre cómo crear la aplicación web, consulta la [Guía de empaquetado para Web](https://flet.dev/docs/publish/web/).
