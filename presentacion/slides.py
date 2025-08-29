#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Descarga imágenes remotas usadas en HTML:
 - <img src="...">
 - url(...) en estilos inline, CSS embebido o scripts

Guarda en ./images con el formato: <nombre_html>-<n>.<ext>
y reemplaza las rutas en el HTML.
"""

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError, ContentTooShortError
import argparse
import shutil
import sys
import re

VALID_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"}
CT_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/bmp": ".bmp",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def read_text_best_effort(p: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return p.read_text(encoding=enc)
        except Exception:
            continue
    return p.read_text(encoding="utf-8", errors="replace")

def write_text_best_effort(p: Path, content: str):
    p.write_text(content, encoding="utf-8")

def get_ext_from_url(url: str) -> str | None:
    ext = Path(urlparse(url).path).suffix.lower()
    if ext in VALID_EXTS:
        return ".jpg" if ext == ".jpeg" else ext
    return None

def ext_from_content_type(ct: str | None) -> str | None:
    if not ct:
        return None
    return CT_TO_EXT.get(ct.split(";")[0].strip().lower())

def download_image(url: str, dest_base: Path, timeout: int = 25) -> Path | None:
    ext = get_ext_from_url(url)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if not ext:
                ext = ext_from_content_type(resp.headers.get("Content-Type")) or ".jpg"
    except (HTTPError, URLError, TimeoutError, ContentTooShortError) as e:
        print(f"  ⚠️  No se pudo descargar {url}: {e}")
        return None
    except Exception as e:
        print(f"  ⚠️  Error inesperado descargando {url}: {e}")
        return None

    final_path = dest_base.with_suffix(ext)
    try:
        final_path.write_bytes(data)
    except Exception as e:
        print(f"  ⚠️  No se pudo escribir {final_path}: {e}")
        return None
    return final_path

def process_html_file(html_path: Path, images_dir: Path, backup_dir: Path):
    print(f"\n📄 Procesando: {html_path.name}")
    ensure_dir(images_dir)
    ensure_dir(backup_dir)

    backup_path = backup_dir / html_path.name
    if not backup_path.exists():
        shutil.copy2(html_path, backup_path)

    content = read_text_best_effort(html_path)
    
    # --- INICIO DE LA CORRECCIÓN ---
    styles_added = False # Usamos una bandera para saber si se hizo esta acción
    if html_path.stem.isdigit():
        style_to_add = """
    <style>
        html, body {
            height: 100%;
            margin: 0;
            padding: 0;
            overflow: hidden; /* Evita barras de scroll innecesarias */
        }
        body {
            display: flex;
            justify-content: center;
            align-items: center;
        }
    </style>"""
        closing_head_pattern = re.compile(r'</head>', re.IGNORECASE)
        new_content, num_replacements = closing_head_pattern.subn(f"{style_to_add}\n</head>", content, count=1)
        
        if num_replacements > 0:
            content = new_content
            print(f"  🎨 Estilos CSS añadidos a {html_path.name}")
            styles_added = True # Marcamos la bandera como verdadera
        else:
            print(f"  ⚠️  No se encontró </head> en {html_path.name}. No se añadieron los estilos.")
    # --- FIN DE LA CORRECCIÓN ---

    stem = html_path.stem
    idx = 1

    def handle_url(url: str) -> str | None:
        nonlocal idx
        if not url.lower().startswith(("http://", "https://")):
            return None
        base_name = f"{stem}-{idx}"
        dest_base = images_dir / base_name
        saved_path = download_image(url, dest_base)
        if saved_path:
            idx += 1
            return f"{images_dir.name}/{saved_path.name}"
        return None

    def repl_img(match: re.Match) -> str:
        prefix, quote, url, _ = match.groups()
        new_src = handle_url(url.strip())
        return f"{prefix}{quote}{new_src}{quote}" if new_src else match.group(0)

    pattern_img = re.compile(r'(<img\b[^>]*?\bsrc\s*=\s*)(["\'])([^"\']+)(\2)', re.IGNORECASE)
    content = pattern_img.sub(repl_img, content)

    def repl_css_fixed(m: re.Match) -> str:
        prefix, quote, url, _, close = m.groups()
        new_src = handle_url(url.strip())
        return f"{prefix}{quote}{new_src}{quote}{close}" if new_src else m.group(0)

    pattern_css = re.compile(r'(\burl\s*\(\s*)(["\']?)([^)"\']+)(\2)(\s*\))', re.IGNORECASE)
    content = pattern_css.sub(repl_css_fixed, content)

    write_text_best_effort(html_path, content)
    
    images_downloaded = idx - 1
    if images_downloaded > 0:
        print(f"  💾 Actualizado: {html_path.name} (imágenes descargadas: {images_downloaded})")
    elif not styles_added: # Si no se descargaron imágenes NI se añadieron estilos
        print("  ℹ️  No se encontraron imágenes remotas ni se realizaron otras acciones.")

def main():
    parser = argparse.ArgumentParser(description="Descarga imágenes remotas en HTML y añade estilos a ficheros numéricos.")
    parser.add_argument("--dir", type=str, default=".", help="Carpeta con los .html (por defecto: .)")
    parser.add_argument("--images", type=str, default="images", help="Carpeta destino de imágenes")
    parser.add_argument("--backup", type=str, default="_old", help="Carpeta de copias de seguridad")
    args = parser.parse_args()

    root = Path(args.dir).resolve()
    images_dir = root / args.images
    backup_dir = root / args.backup

    html_files = sorted(root.glob("*.html"))
    if not html_files:
        print(f"ℹ️  No se encontraron ficheros .html en {root}")
        return

    for html in html_files:
        process_html_file(html, images_dir, backup_dir)

if __name__ == "__main__":
    main()
	