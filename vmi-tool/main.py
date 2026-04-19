import re
import traceback
import unicodedata
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from processors import robo, savings, trading
from vmi_excel import generate_vmi_excel

app = FastAPI(title="VMI Investicinės Sąskaitos Konverteris")

static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


DOMAIN = "https://vmikonverteris-production.up.railway.app"


@app.get("/", response_class=HTMLResponse)
async def index():
    return (static_path / "index.html").read_text(encoding="utf-8")


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    return f"User-agent: *\nAllow: /\nSitemap: {DOMAIN}/sitemap.xml\n"


@app.get("/sitemap.xml", response_class=Response)
async def sitemap():
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{DOMAIN}/</loc>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    return Response(content=content, media_type="application/xml")


@app.post("/api/process")
async def process(
    account_number: str = Form(...),
    account_type: str = Form(...),
    year: int = Form(default=2025),
    file: UploadFile = File(...),
):
    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1")

    try:
        if account_type == "trading":
            rows = trading.process(content, year)
        elif account_type == "savings":
            rows = savings.process(content, year)
        elif account_type == "robo":
            rows = robo.process(content, year)
        else:
            raise HTTPException(status_code=400, detail=f"Nežinomas sąskaitos tipas: {account_type!r}")
    except HTTPException:
        raise
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=422, detail=f"CSV apdorojimo klaida: {exc}") from exc

    if not rows:
        raise HTTPException(
            status_code=422,
            detail=f"Nerasta jokių tinkamų įrašų {year} metams pasirinktame CSV faile.",
        )

    xlsx_bytes = generate_vmi_excel(account_number, rows)

    safe_num = re.sub(r"[^\w]", "_", account_number)
    safe_num = _to_ascii(safe_num)
    filename = f"VMI_{safe_num}_{year}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Row-Count": str(len(rows)),
            "X-Filename": filename,
        },
    )


def _to_ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
