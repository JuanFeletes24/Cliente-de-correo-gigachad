import flet as ft
import markdownify
import asyncio

from modules.email import (
    ImapEmail,
    PopEmail,
    SmtpSender,
    update_config_file,
    config,
)
from modules import db

from pathlib import Path
from bs4 import BeautifulSoup

import webbrowser
import tempfile
import os


SAMPLE_TEXT = """### Bienvenido a tu Cliente de Correo

Selecciona un correo de la lista a la izquierda para ver su contenido aquí.
"""


def format_email_body(raw_body):
    if "<" not in raw_body or ">" not in raw_body:
        return raw_body

    try:
        soup = BeautifulSoup(
            raw_body,
            "html.parser",
        )

        for tag in soup([
            "script",
            "style",
            "head",
            "meta",
            "link",
            "noscript",
        ]):
            tag.decompose()

        # Eliminar algunos elementos explícitamente ocultos
        for tag in soup.select(
            '[style*="display:none"], '
            '[style*="display: none"], '
            '[hidden]'
        ):
            tag.decompose()

        text = soup.get_text(
            separator="\n",
            strip=True,
        )

        # Eliminar líneas vacías repetidas
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        return "\n\n".join(lines)

    except Exception:
        return raw_body
    
def show_inbox(page: ft.Page):
    page.title = "Redes de Computadores: Proyecto 1"

    page.clean()

    current_selected_email = {
        "html": "",
        "subject": "",
    }
    body_request = {"id": 0}
    sync_lock = asyncio.Lock()

    # Header y contenido del panel derecho
    selected_subject = ft.Text(
        "Bienvenido a tu Cliente de Correo",
        size=20,
        weight=ft.FontWeight.BOLD,
    )

    selected_from = ft.Text(
        "",
        color=ft.Colors.OUTLINE,
        size=13,
    )

    selected_date = ft.Text(
        "",
        color=ft.Colors.OUTLINE,
        size=11,
    )

    def open_in_browser(e):
        html_code = current_selected_email.get("html", "")

        if not html_code:
            page.show_dialog(
                ft.SnackBar(
                    ft.Text("No hay ningún correo seleccionado.")
                )
            )
            return

        # Envolver en estructura HTML si es texto plano
        if (
            "<html" not in html_code.lower()
            and "<body" not in html_code.lower()
        ):
            full_html = (
                "<!DOCTYPE html>"
                "<html>"
                "<head>"
                "<meta charset='utf-8'>"
                f"<title>{current_selected_email.get('subject', 'Correo')}</title>"
                "<style>"
                "body{font-family:Segoe UI, sans-serif;"
                "padding:24px;line-height:1.6;}"
                "</style>"
                "</head>"
                "<body>"
                "<pre style='white-space: pre-wrap; font-family: inherit;'>"
                f"{html_code}"
                "</pre>"
                "</body>"
                "</html>"
            )
        else:
            full_html = html_code

        temp_dir = tempfile.gettempdir()

        temp_file = os.path.join(
            temp_dir,
            "correo_completo.html",
        )

        with open(
            temp_file,
            "w",
            encoding="utf-8",
        ) as f:
            f.write(full_html)

        webbrowser.open(
            f"file://{temp_file}"
        )

        page.show_dialog(
            ft.SnackBar(
                ft.Text(
                    "Abriendo correo en el navegador..."
                )
            )
        )

    btn_open_browser = ft.Button(
        "Ver HTML original en Navegador",
        icon=ft.Icons.OPEN_IN_BROWSER,
        visible=False,
        on_click=open_in_browser,
    )

    # Contenedor Markdown para el cuerpo del correo
    markdown_cont = ft.Markdown(
        SAMPLE_TEXT,
        extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
        selectable=True,
    )

    normal_right_content = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            selected_subject,
            selected_from,
            ft.Row(
                [
                    selected_date,
                    btn_open_browser,
                ],
                alignment=(
                    ft.MainAxisAlignment
                    .SPACE_BETWEEN
                ),
            ),
            ft.Divider(),
            markdown_cont,
        ],
    )

    def notify(msg: str):
        page.show_dialog(
            ft.SnackBar(
                ft.Text(msg)
            )
        )

    def show_body(email_data: dict):
        async def handle_click(e):
            body_request["id"] += 1
            request_id = body_request["id"]

            current_selected_email["html"] = (
                email_data.get("body", "") or ""
            )

            current_selected_email["subject"] = (
                email_data.get(
                    "subject",
                    "Correo",
                )
            )

            selected_subject.value = (
                email_data.get("subject")
                or "(Sin Asunto)"
            )

            selected_from.value = (
                f"De: {email_data.get('from', '(Desconocido)')}"
            )

            selected_date.value = (
                f"Fecha: {email_data.get('date', '')}"
            )

            btn_open_browser.visible = True
            right_column.content = normal_right_content

            raw_body = (
                email_data.get("body", "")
                or ""
            )

            markdown_cont.value = "*Procesando correo...*"
            page.update()

            md_text = await asyncio.to_thread(
                format_email_body,
                raw_body,
            )

            if request_id != body_request["id"]:
                return

            markdown_cont.value = (
                md_text.strip()
                or "*(Cuerpo del correo vacío)*"
            )

            page.update()

        return handle_click

    def email_card(email_data: dict) -> ft.Control:
        subject_row = [
            ft.Text(
                email_data.get("subject") or "(Sin Asunto)",
                weight=ft.FontWeight.BOLD,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
                expand=True,  # empuja el badge a la derecha
            ),
        ]

        if email_data.get("is_new"):
            subject_row.append(
                ft.Container(
                    content=ft.Text("Nuevo", size=10, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.RED,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                )
            )

        return ft.Container(
            padding=12,
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ink=True,
            on_click=show_body(email_data),
            content=ft.Column(
                spacing=2,
                controls=[
                    ft.Row(
                        subject_row,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(
                        email_data.get("from") or "(Desconocido)",
                        color=ft.Colors.OUTLINE,
                        size=12,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        email_data.get("date") or "",
                        color=ft.Colors.OUTLINE,
                        size=10,
                        max_lines=1,
                    ),
                ],
            ),
        )

        if not email_data.get("is_new"):
            return card

        return ft.Stack(
            clip_behavior=ft.ClipBehavior.NONE,
            controls=[
                card,
                ft.Container(
                    content=ft.Text(
                        "Nuevo",
                        size=10,
                        color=ft.Colors.WHITE,
                    ),
                    bgcolor=ft.Colors.RED,
                    padding=ft.Padding.symmetric(
                        horizontal=6,
                        vertical=2,
                    ),
                    border_radius=4,
                    top=-6,
                    right=-6,
                ),
            ],
        )

    left_column = ft.Column(
        expand=35,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,  # nuevo
        controls=[],
    )

    def load_emails_from_db():
        account = config.get(
            "auth",
            "user",
            fallback="",
        )

        emails = db.get_all_emails(
            account
        )

        left_column.controls.clear()

        if not emails:
            left_column.controls.append(
                ft.Container(
                    padding=20,
                    content=ft.Text(
                        "No hay correos descargados. "
                        "Haz clic en Refrescar o Configuración.",
                        color=ft.Colors.OUTLINE,
                    ),
                )
            )

        else:
            for em in emails:
                left_column.controls.append(
                    email_card(em)
                )

        page.update()

    def sync_emails_once():
        protocol = config.get(
            "app",
            "protocol",
            fallback="imap",
        ).lower()

        if protocol == "imap":
            ImapEmail().get_emails()
        else:
            PopEmail().get_mails()

    async def perform_sync(manual=False):
        if sync_lock.locked():
            if manual:
                notify("Ya hay una sincronización en curso.")
            return

        async with sync_lock:
            if manual:
                protocol = config.get(
                    "app",
                    "protocol",
                    fallback="imap",
                ).upper()
                notify(f"Descargando correos vía {protocol}...")

            try:
                await asyncio.to_thread(sync_emails_once)
                load_emails_from_db()

                if manual:
                    notify(
                        "Bandeja de entrada "
                        "sincronizada con éxito."
                    )

            except Exception as ex:
                if manual:
                    notify(f"Error al sincronizar: {ex}")
                else:
                    print(f"Error de sincronización automática: {ex}")

            page.update()

    async def refresh_emails(e):
        await perform_sync(manual=True)

    async def auto_sync_worker():
        while True:
            await perform_sync()
            await asyncio.sleep(60)

    # ----------------------------------
    # CONFIGURACIÓN
    # ----------------------------------

    def open_settings(e):
        conf_user = ft.TextField(
            label="Usuario (Correo)",
            value=config.get(
                "auth",
                "user",
                fallback="",
            ),
        )

        conf_pass = ft.TextField(
            label="Contraseña de Aplicación",
            value=config.get(
                "auth",
                "password",
                fallback="",
            ),
            password=True,
            can_reveal_password=True,
        )

        conf_protocol = ft.Dropdown(
            label="Protocolo",
            value=config.get(
                "app",
                "protocol",
                fallback="imap",
            ),
            options=[
                ft.dropdown.Option("imap"),
                ft.dropdown.Option("pop"),
            ],
        )

        conf_days = ft.TextField(
            label="Período de descarga (Días)",
            value=config.get(
                "app",
                "days",
                fallback="14",
            ),
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        conf_imap_sv = ft.TextField(
            label="Servidor IMAP",
            value=config.get(
                "imap",
                "server",
                fallback="imap.gmail.com",
            ),
            expand=True,
        )

        conf_imap_pt = ft.TextField(
            label="Puerto IMAP",
            value=config.get(
                "imap",
                "port",
                fallback="993",
            ),
            width=100,
        )

        conf_pop_sv = ft.TextField(
            label="Servidor POP",
            value=config.get(
                "pop",
                "server",
                fallback="pop.gmail.com",
            ),
            expand=True,
        )

        conf_pop_pt = ft.TextField(
            label="Puerto POP",
            value=config.get(
                "pop",
                "port",
                fallback="995",
            ),
            width=100,
        )

        conf_smtp_sv = ft.TextField(
            label="Servidor SMTP",
            value=config.get(
                "smtp",
                "server",
                fallback="smtp.gmail.com",
            ),
            expand=True,
        )

        conf_smtp_pt = ft.TextField(
            label="Puerto SMTP",
            value=config.get(
                "smtp",
                "port",
                fallback="465",
            ),
            width=100,
        )

        def save_and_close(ev):
            new_conf = {
                "auth": {
                    "user": conf_user.value,
                    "password": conf_pass.value,
                },
                "app": {
                    "protocol": conf_protocol.value,
                    "days": conf_days.value,
                },
                "imap": {
                    "server": conf_imap_sv.value,
                    "port": conf_imap_pt.value,
                },
                "pop": {
                    "server": conf_pop_sv.value,
                    "port": conf_pop_pt.value,
                },
                "smtp": {
                    "server": conf_smtp_sv.value,
                    "port": conf_smtp_pt.value,
                },
            }

            update_config_file(
                new_conf
            )

            config.read(
                Path(__file__).parent.parent
                / "modules"
                / "email_config.ini"
            )

            page.pop_dialog()

            notify(
                "Configuración guardada."
            )

            load_emails_from_db()

        dlg = ft.AlertDialog(
            title=ft.Text(
                "Configuración de Correo"
            ),
            content=ft.Column(
                [
                    conf_user,
                    conf_pass,
                    ft.Row([
                        conf_protocol,
                        conf_days,
                    ]),
                    ft.Row([
                        conf_imap_sv,
                        conf_imap_pt,
                    ]),
                    ft.Row([
                        conf_pop_sv,
                        conf_pop_pt,
                    ]),
                    ft.Row([
                        conf_smtp_sv,
                        conf_smtp_pt,
                    ]),
                ],
                scroll=ft.ScrollMode.AUTO,
                tight=True,
                width=450,
            ),
            actions=[
                ft.TextButton(
                    "Cancelar",
                    on_click=lambda ev:
                    page.pop_dialog(),
                ),
                ft.FilledButton(
                    "Guardar",
                    on_click=save_and_close,
                ),
            ],
        )

        page.show_dialog(dlg)

    # ----------------------------------
    # CONTACTOS / CLAVES
    # ----------------------------------

    def open_contacts(e):
        contact_email = ft.TextField(
            label="Correo del Contacto",
            expand=True,
        )

        contact_key = ft.TextField(
            label="Clave secreta (Cifrado)",
            password=True,
            can_reveal_password=True,
            expand=True,
        )

        contacts_list = ft.Column(
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
            height=120,
        )

        def refresh_contacts_view():
            contacts_list.controls.clear()

            stored = db.get_all_contacts()

            if not stored:
                contacts_list.controls.append(
                    ft.Text(
                        "No hay contactos "
                        "con claves registradas.",
                        size=12,
                        color=ft.Colors.OUTLINE,
                    )
                )

            else:
                for c in stored:
                    contacts_list.controls.append(
                        ft.Text(
                            f"• {c['email']} "
                            "(Clave configurada)",
                            size=12,
                        )
                    )

            page.update()

        def save_key(ev):
            if (
                contact_email.value
                and contact_key.value
            ):
                db.save_contact_key(
                    contact_email.value.strip(),
                    contact_key.value.strip(),
                )

                contact_email.value = ""
                contact_key.value = ""

                refresh_contacts_view()

                notify(
                    "Clave guardada "
                    "para el contacto."
                )

            else:
                notify(
                    "Ingresa el correo "
                    "y la clave."
                )

        dlg = ft.AlertDialog(
            title=ft.Text(
                "Claves de Cifrado por Contacto"
            ),
            content=ft.Column(
                [
                    ft.Text(
                        "Configura una clave por "
                        "contacto para enviar mensajes "
                        "cifrados y descifrar los recibidos.",
                        size=13,
                    ),
                    ft.Row([
                        contact_email
                    ]),
                    ft.Row([
                        contact_key
                    ]),
                    ft.FilledButton(
                        "Guardar Clave",
                        on_click=save_key,
                    ),
                    ft.Divider(),
                    ft.Text(
                        "Contactos guardados:",
                        weight=ft.FontWeight.BOLD,
                        size=13,
                    ),
                    contacts_list,
                ],
                tight=True,
                width=450,
            ),
            actions=[
                ft.TextButton(
                    "Cerrar",
                    on_click=lambda ev:
                    page.pop_dialog(),
                ),
            ],
        )

        refresh_contacts_view()

        page.show_dialog(dlg)

    # ----------------------------------
    # REDACTAR
    # ----------------------------------

    def open_compose(e):
        comp_to = ft.TextField(
            label="Para (Destinatario)"
        )

        comp_subject = ft.TextField(
            label="Asunto"
        )

        comp_body = ft.TextField(
            label="Mensaje",
            multiline=True,
            min_lines=5,
            max_lines=8,
        )

        send_button = ft.FilledButton("Enviar")

        def close_compose(ev=None):
            right_column.content = normal_right_content
            page.update()

        async def send_action(ev):
            if (
                not comp_to.value
                or not comp_subject.value
            ):
                notify(
                    "Completa el destinatario "
                    "y asunto."
                )
                return

            notify(
                "Enviando correo..."
            )
            send_button.disabled = True
            page.update()

            try:
                sender = SmtpSender()
                success, msg = await asyncio.to_thread(
                    sender.send_email,
                    comp_to.value.strip(),
                    comp_subject.value.strip(),
                    comp_body.value,
                )
            except Exception as ex:
                success, msg = False, str(ex)

            if success:
                notify(
                    "¡Correo enviado con éxito!"
                )

                close_compose()

            else:
                send_button.disabled = False
                notify(
                    f"Error al enviar: {msg}"
                )

            page.update()

        send_button.on_click = send_action

        right_column.content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text(
                    "Nuevo correo",
                    size=20,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Divider(),
                comp_to,
                comp_subject,
                comp_body,
                ft.Row(
                    controls=[
                        ft.TextButton(
                            "Cancelar",
                            on_click=close_compose,
                        ),
                        send_button,
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
        )
        page.update()

    # ----------------------------------
    # APP BAR
    # ----------------------------------

    page.appbar = ft.AppBar(
        title=ft.Text(
            "Bandeja de Entrada"
        ),
        center_title=True,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        actions=[
            ft.IconButton(
                ft.Icons.REFRESH,
                on_click=refresh_emails,
                tooltip="Sincronizar correos",
            ),
            ft.IconButton(
                ft.Icons.LOCK,
                on_click=open_contacts,
                tooltip="Claves de Contactos",
            ),
            ft.IconButton(
                ft.Icons.SETTINGS,
                on_click=open_settings,
                tooltip="Configuración",
            ),
        ],
    )

    # Botón flotante para redactar
    page.floating_action_button = (
        ft.FloatingActionButton(
            icon=ft.Icons.ADD,
            on_click=open_compose,
            tooltip="Redactar nuevo correo",
        )
    )

    right_column = ft.Container(
        expand=65,
        alignment=ft.Alignment(-1, -1),
        padding=16,
        border_radius=8,
        border=ft.Border(
            left=ft.BorderSide(
                2,
                ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ),
            top=ft.BorderSide(
                2,
                ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ),
            right=ft.BorderSide(
                2,
                ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ),
            bottom=ft.BorderSide(
                2,
                ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ),
        ),
        content=normal_right_content,
    )

    page.add(
        ft.Row(
            expand=True,
            controls=[
                left_column,
                right_column,
            ],
        )
    )

    # Cargar correos iniciales
    # desde base de datos local
    load_emails_from_db()
    page.run_task(auto_sync_worker)
