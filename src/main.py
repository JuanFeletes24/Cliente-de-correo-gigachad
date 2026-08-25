import flet as ft
from modules.email import ImapEmail, PopEmail

EMAILS = [
    {"id":0, "subject": "El proyecto era para HOY?", "from": "estudiante1@urosario.edu.co", "is_new": False, "body": "Siiii, Y ahora que hacemos?"},
    {"id":1, "subject": "El profe está enamorado de Linux", "from": "estudiante2@urosario.edu.co", "is_new": True, "body": "Siiii"},
    {"id":2, "subject": "El lunes hay clase?", "from": "estudiante3@urosario.edu.co", "is_new": False, "body": "No, es festivo"},
]


SAMPLE_HTML = """Si quieres leer un mensaje:

    Clic en el botón leer
"""

def main(page: ft.Page):
    page.title = "Redes de Computadores: Proyecto 1"
    page.appbar = ft.AppBar(title=ft.Text("Bandeja de Entrada"), center_title=True)

    markdown_cont = ft.Markdown(SAMPLE_HTML, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED)

    def show_body(email_id: int):
        def handle_click(e: ft.Event[ft.Button]):
            email = EMAILS[email_id]
            page.show_dialog(ft.SnackBar(ft.Text(f"Mostrando {email['subject']}")))
            markdown_cont.value = email['body']
            page.update()

        return handle_click

    def email_card(email: dict) -> ft.Control:
        card = ft.Container(
            padding=12,
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text(email["subject"], weight=ft.FontWeight.BOLD),
                            ft.Text(email["from"], color=ft.Colors.OUTLINE),
                        ],
                    ),
                    ft.Button("Leer", on_click=show_body(email["id"])),
                ],
            ),
        )
        if not email["is_new"]:
            return card
        return ft.Stack(
            clip_behavior=ft.ClipBehavior.NONE,
            controls=[
                card,
                ft.Container(
                    content=ft.Text("Nuevo", size=10, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.RED,
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                    top=-6,
                    right=-6,
                ),
            ],
        )


    left_column = ft.Column(
        expand=35,
        controls=[email_card(email) for email in EMAILS],
    )
    right_column = ft.Container(
        expand=65,
        alignment=ft.Alignment(-1, -1),
        # padding=ft.Padding.only(left=20),
        padding=12,
        border_radius=8,
        border=ft.Border(
            left=ft.BorderSide(2, ft.Colors.SURFACE_CONTAINER_HIGHEST),
            top=ft.BorderSide(2, ft.Colors.SURFACE_CONTAINER_HIGHEST),
            right=ft.BorderSide(2, ft.Colors.SURFACE_CONTAINER_HIGHEST),
            bottom=ft.BorderSide(2, ft.Colors.SURFACE_CONTAINER_HIGHEST),
        ),
        content=markdown_cont,
    )
    page.add(
        ft.Row(
            expand=True,
            controls=[left_column, right_column],
        ),
    )


if __name__ == "__main__":
    # imap_email = ImapEmail()
    # imap_email.get_emails()
    # pop_email = PopEmail()
    # pop_email.get_mails()
    ft.run(main)

