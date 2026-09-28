"""AGRO - plantilla base de pagina."""
PAGE_CSS = (
    "body{font-family:system-ui,sans-serif;"
    "background:#0d1117;color:#e6edf3;"
    "display:flex;justify-content:center;"
    "padding:20px;margin:0}"
    ".wrap{max-width:680px;width:100%}"
    "h1{font-size:1.3rem}"
    ".card{background:#161b22;"
    "border:1px solid #30363d;"
    "border-radius:10px;padding:14px;"
    "margin-top:10px}"
    "button{background:#238636;color:#fff;"
    "border:none;padding:12px 18px;"
    "border-radius:8px;width:100%}"
)


def render_page(title, body):
    return (
        "<!DOCTYPE html><html lang='es'>"
        "<head><meta charset='utf-8'>"
        "<meta name='viewport' content="
        "'width=device-width, initial-scale=1'>"
        "<title>" + str(title) + "</title>"
        "<style>" + PAGE_CSS + "</style>"
        "</head><body><div class='wrap'>"
        + str(body)
        + "</div></body></html>"
    )
