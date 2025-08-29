#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Descarga imágenes remotas referenciadas en ficheros HTML y actualiza las rutas.
- Guarda cada imagen en ./images con el formato: <nombre_html>-<n>.<ext>
- Reemplaza el src de <img> por "images/<nombre_html>-<n>.<ext>"
- Hace copia del HTML original en ./_old
- Solo procesa imágenes remotas (http/https)
Uso:
    python descargar_imagenes_html.py --dir "ruta/a/carpeta"   # por defecto: carpeta actual
"""

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError, ContentTooShortError
import argparse
import shutil
import sys
import re

# Extensiones válidas que intentaremos respetar
VALID_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"}

# Mapear Content-Type -> extensión si la URL no trae extensión
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

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def read_text_best_effort(p: Path) -> str:
    # Intento en UTF-8, si falla pruebo latin-1 (común en Windows)
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return p.read_text(encoding=enc)
        except Exception:
            continue
    # Último recurso: leer con errores reemplazados
    return p.read_text(encoding="utf-8", errors="replace")

def write_text_best_effort(p: Path, content: str):
    # Guardamos siempre en UTF-8
    p.write_text(content, encoding="utf-8")

def get_ext_from_url(url: str) -> str | None:
    path = urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext in VALID_EXTS:
        # Normalizamos .jpeg -> .jpg
        return ".jpg" if ext == ".jpeg" else ext
    return None

def ext_from_content_type(ct: str | None) -> str | None:
    if not ct:
        return None
    ct = ct.split(";")[0].strip().lower()
    return CT_TO_EXT.get(ct)

def download_image(url: str, dest_base: Path, timeout: int = 25) -> Path | None:
    """
    Descarga 'url' y guarda en un fichero con la extensión adecuada.
    dest_base: ruta base SIN extensión (p.ej. images/2-1)
    Devuelve la ruta final (con extensión) o None si falla.
    """
    # Primera pista: extensión de la URL
    ext = get_ext_from_url(url)

    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            # Si no teníamos extensión, inferimos por Content-Type
            if not ext:
                ext = ext_from_content_type(resp.headers.get("Content-Type")) or ".jpg"
    except (HTTPError, URLError, TimeoutError, ContentTooShortError) as e:
        print(f"  ⚠️  No se pudo descargar {url}: {e}")
        return None
    except Exception as e:
        print(f"  ⚠️  Error inesperado descargando {url}: {e}")
        return None

    # Nombre final con extensión
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

    # Copia de seguridad (no sobrescribe si ya existe una copia idéntica)
    backup_path = backup_dir / html_path.name
    try:
        if not backup_path.exists():
            shutil.copy2(html_path, backup_path)
    except Exception as e:
        print(f"  ⚠️  No se pudo crear copia en _old: {e}")

    content = read_text_best_effort(html_path)
    stem = html_path.stem

    # Patrón para localizar el valor del src y poder sustituir SOLO esa parte.
    # Capturas:
    #  1) prefijo "<img ... src="
    #  2) comilla de apertura
    #  3) valor de src
    #  4) comilla de cierre (igual que 2)
    pattern = re.compile(r'(<img\b[^>]*?\bsrc\s*=\s*)(["\'])([^"\']+)(\2)', re.IGNORECASE | re.DOTALL)

    idx = 1  # contador de imágenes por orden de aparición

    def repl(match: re.Match) -> str:
        nonlocal idx
        prefix, quote, url, _ = match.groups()
        url_clean = url.strip()

        # Solo URLs remotas
        if not url_clean.lower().startswith(("http://", "https://")):
            return match.group(0)

        base_name = f"{stem}-{idx}"
        dest_base = images_dir / base_name

        saved_path = download_image(url_clean, dest_base)
        if not saved_path:
            # Si no se pudo descargar, no tocamos el HTML
            return match.group(0)

        # Éxito: incrementamos el índice y reemplazamos el src
        idx += 1
        new_src = f"{images_dir.name}/{saved_path.name}"  # "images/2-1.png"
        print(f"  ✅ {url_clean}  →  {new_src}")
        return f"{prefix}{quote}{new_src}{quote}"

    # Ejecutamos los reemplazos
    try:
        new_content = pattern.sub(repl, content)
    except Exception as e:
        print(f"  ⚠️  Error procesando {html_path.name}: {e}")
        return

    # Guardamos el HTML modificado
    try:
        write_text_best_effort(html_path, new_content)
        if idx == 1:
            print("  ℹ️  No se encontraron imágenes remotas para descargar.")
        else:
            print(f"  💾 Actualizado: {html_path.name} (imágenes descargadas: {idx-1})")
    except Exception as e:
        print(f"  ⚠️  No se pudo escribir el HTML actualizado: {e}")

def main():
    parser = argparse.ArgumentParser(description="Descarga imágenes remotas de ficheros HTML y actualiza sus rutas.")
    parser.add_argument("--dir", type=str, default=".", help="Carpeta con los .html (por defecto: .)")
    parser.add_argument("--images", type=str, default="images", help="Carpeta destino de imágenes (por defecto: images)")
    parser.add_argument("--backup", type=str, default="_old", help="Carpeta de copias de seguridad (por defecto: _old)")
    args = parser.parse_args()

    root = Path(args.dir).resolve()
    images_dir = root / args.images
    backup_dir = root / args.backup

    if not root.exists():
        print(f"❌ La carpeta indicada no existe: {root}")
        sys.exit(1)

    html_files = sorted(root.glob("*.html"))
    if not html_files:
        print(f"ℹ️  No se encontraron ficheros .html en {root}")
        return

    print(f"🔎 Carpeta: {root}")
    print(f"🖼️  Carpeta de imágenes: {images_dir}")
    print(f"🗂️  Copias de seguridad: {backup_dir}")

    for html in html_files:
        process_html_file(html, images_dir, backup_dir)

if __name__ == "__main__":
    main()
