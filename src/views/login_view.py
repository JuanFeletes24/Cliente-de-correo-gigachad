import flet as ft

from modules.email import config, update_config_file


def show_login(page: ft.Page, on_success):
    page.title = "Redes de Computadores: Proyecto 1"

    # Limpiar elementos que puedan venir de otra vista
    page.clean()
    page.appbar = None
    page.floating_action_button = None

    conf_user = ft.TextField(
        label="Usuario (Correo)",
        value=config.get("auth", "user", fallback=""),
    )

    conf_pass = ft.TextField(
        label="Contraseña de Aplicación",
        value=config.get("auth", "password", fallback=""),
        password=True,
        can_reveal_password=True,
    )

    conf_protocol = ft.Dropdown(
        label="Protocolo",
        value=config.get("app", "protocol", fallback="imap"),
        options=[
            ft.dropdown.Option("imap"),
            ft.dropdown.Option("pop"),
        ],
    )

    conf_days = ft.TextField(
        label="Período de descarga (Días)",
        value=config.get("app", "days", fallback="14"),
        keyboard_type=ft.KeyboardType.NUMBER,
    )

    conf_imap_sv = ft.TextField(
        label="Servidor IMAP",
        value=config.get("imap", "server", fallback="imap.gmail.com"),
        expand=True,
    )

    conf_imap_pt = ft.TextField(
        label="Puerto IMAP",
        value=config.get("imap", "port", fallback="993"),
        width=100,
    )

    conf_pop_sv = ft.TextField(
        label="Servidor POP",
        value=config.get("pop", "server", fallback="pop.gmail.com"),
        expand=True,
    )

    conf_pop_pt = ft.TextField(
        label="Puerto POP",
        value=config.get("pop", "port", fallback="995"),
        width=100,
    )

    conf_smtp_sv = ft.TextField(
        label="Servidor SMTP",
        value=config.get("smtp", "server", fallback="smtp.gmail.com"),
        expand=True,
    )

    conf_smtp_pt = ft.TextField(
        label="Puerto SMTP",
        value=config.get("smtp", "port", fallback="465"),
        width=100,
    )

    def notify(msg: str):
        page.show_dialog(
            ft.SnackBar(
                ft.Text(msg)
            )
        )

    def login(ev):
        if not conf_user.value or not conf_pass.value:
            notify("Ingresa el correo y la contraseña de aplicación.")
            return

        new_conf = {
            "auth": {
                "user": conf_user.value.strip(),
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

        update_config_file(new_conf)

        page.clean()

        on_success(page)

    login_form = ft.Container(
        padding=30,
        border_radius=12,
        border=ft.Border.all(
            1,
            ft.Colors.SURFACE_CONTAINER_HIGHEST,
        ),
        content=ft.Column(
            spacing=15,
            controls=[
                ft.Text(
                    "Cliente de Correo",
                    size=28,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    "Configura tu cuenta para acceder a la bandeja de entrada.",
                    color=ft.Colors.OUTLINE,
                ),

                ft.Divider(),

                conf_user,
                conf_pass,

                ft.ResponsiveRow(
                    controls=[
                        ft.Container(
                            content=conf_protocol,
                            col={
                                "xs": 12,
                                "sm": 6,
                            },
                        ),
                        ft.Container(
                            content=conf_days,
                            col={
                                "xs": 12,
                                "sm": 6,
                            },
                        ),
                    ],
                ),

                ft.Divider(),

                ft.Text(
                    "Configuración de servidores",
                    weight=ft.FontWeight.BOLD,
                ),

                ft.ResponsiveRow(
                    controls=[
                        ft.Container(
                            content=conf_imap_sv,
                            col={
                                "xs": 12,
                                "sm": 9,
                            },
                        ),
                        ft.Container(
                            content=conf_imap_pt,
                            col={
                                "xs": 12,
                                "sm": 3,
                            },
                        ),
                    ],
                ),

                ft.ResponsiveRow(
                    controls=[
                        ft.Container(
                            content=conf_pop_sv,
                            col={
                                "xs": 12,
                                "sm": 9,
                            },
                        ),
                        ft.Container(
                            content=conf_pop_pt,
                            col={
                                "xs": 12,
                                "sm": 3,
                            },
                        ),
                    ],
                ),

                ft.ResponsiveRow(
                    controls=[
                        ft.Container(
                            content=conf_smtp_sv,
                            col={
                                "xs": 12,
                                "sm": 9,
                            },
                        ),
                        ft.Container(
                            content=conf_smtp_pt,
                            col={
                                "xs": 12,
                                "sm": 3,
                            },
                        ),
                    ],
                ),

                ft.FilledButton(
                    "Iniciar sesión",
                    icon=ft.Icons.LOGIN,
                    on_click=login,
                ),
            ],
        ),
    )
    page.add(
        ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    padding=20,
                    content=ft.ResponsiveRow(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                content=login_form,
                                col={
                                    "xs": 12,
                                    "sm": 10,
                                    "md": 8,
                                    "lg": 6,
                                    "xl": 5,
                                },
                            ),
                        ],
                    ),
                ),
            ],
        )
    )