import flet as ft

from modules.email import config
from views.login_view import show_login
from views.inbox_view import show_inbox


def main(page: ft.Page):
    page.title = "Redes de Computadores: Proyecto 1"

    # Tamaño inicial de escritorio
    page.window.width = 1000
    page.window.height = 720

    # Evitar que la ventana llegue a un tamaño inútil
    page.window.min_width = 600
    page.window.min_height = 500

    user = config.get("auth", "user", fallback="")
    password = config.get("auth", "password", fallback="")

    if user and password:
        show_inbox(page)
    else:
        show_login(page, on_success=show_inbox)


if __name__ == "__main__":
    ft.run(main)