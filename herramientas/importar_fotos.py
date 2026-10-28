#!/usr/bin/env python3
"""Lee fecha, hora y ubicación (EXIF) de las fotos del libro y prepara copias livianas para la página.

Pon las fotos en:  materiales/fotos/nohemi/   materiales/fotos/greg/   materiales/fotos/juntos/
Uso:               python3 herramientas/importar_fotos.py
Requiere una vez:  pip3 install pillow pillow-heif

- Escribe materiales/fotos/fotos.json. Ahí puedes completar a mano "lugar", "pie" y "capitulo";
  al volver a correr el script esos campos se conservan.
- Las copias para la página (materiales/fotos/_web/) se guardan SIN metadatos.
- Las coordenadas GPS van a materiales/fotos/ubicaciones.json, que NO se sube a GitHub.
"""
import sys, json, re
from pathlib import Path
try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Falta Pillow. Instálalo una vez con:\n  pip3 install pillow pillow-heif")
try:
    from pillow_heif import register_heif_opener
    register_heif_opener(); HEIC = True
except ImportError:
    HEIC = False

RAIZ = Path(__file__).resolve().parent.parent
FOT = RAIZ / "materiales" / "fotos"
WEB = FOT / "_web"
IDX = FOT / "fotos.json"
GPS = FOT / "ubicaciones.json"   # privado: está en .gitignore, nunca se sube
EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
QUIEN = {"nohemi": "Nohemi", "greg": "Greg", "juntos": "Juntos"}

def num(x):
    try: return float(x)
    except TypeError: return x[0] / x[1]

def gps(g):
    try:
        dms = lambda v: num(v[0]) + num(v[1]) / 60 + num(v[2]) / 3600
        lat, lon = dms(g[2]), dms(g[4])
        if str(g.get(1, "N")).upper().startswith("S"): lat = -lat
        if str(g.get(3, "E")).upper().startswith("W"): lon = -lon
        return round(lat, 6), round(lon, 6)
    except Exception:
        return None, None

def main():
    previo = json.loads(IDX.read_text(encoding="utf-8")) if IDX.exists() else {}
    ubic = json.loads(GPS.read_text(encoding="utf-8")) if GPS.exists() else {}
    WEB.mkdir(parents=True, exist_ok=True)
    salida, sin_fecha, saltadas = {}, [], []
    for p in sorted(FOT.rglob("*")):
        if p.suffix.lower() not in EXT or WEB in p.parents or p.parent == FOT: continue
        if p.suffix.lower() in (".heic", ".heif") and not HEIC:
            saltadas.append(p.name); continue
        rel = str(p.relative_to(RAIZ))
        e = dict(previo.get(rel, {}))
        try:
            im = Image.open(p); ex = im.getexif()
            sub = ex.get_ifd(0x8769); g = ex.get_ifd(0x8825)
            dt = sub.get(36867) or ex.get(306)
            if dt:
                d, t = str(dt).strip().split(" ")[:2]
                e["fecha"], e["hora"] = d.replace(":", "-"), t[:5]
            lat, lon = gps(g) if g else (None, None)
            if lat is not None: ubic[rel] = {"lat": lat, "lon": lon}
            e.pop("lat", None); e.pop("lon", None)
            web = WEB / (re.sub(r"[^a-zA-Z0-9]+", "-", str(p.relative_to(FOT).with_suffix(""))).strip("-") + ".jpg")
            if not web.exists():
                c = ImageOps.exif_transpose(im).convert("RGB"); c.thumbnail((1400, 1400))
                c.save(web, "JPEG", quality=82)
            e["web"] = str(web.relative_to(RAIZ))
        except Exception as err:
            print(f"  no pude leer {rel}: {err}"); continue
        e["quien"] = QUIEN.get(p.relative_to(FOT).parts[0].lower(), "Juntos")
        for k in ("lugar", "pie", "capitulo"): e.setdefault(k, "")
        if not e.get("fecha"): sin_fecha.append(rel)
        salida[rel] = e
    salida = dict(sorted(salida.items(), key=lambda kv: (kv[1].get("fecha") or "9999", kv[1].get("hora") or "")))
    IDX.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    GPS.write_text(json.dumps(ubic, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(salida)} fotos en materiales/fotos/fotos.json.")
    if sin_fecha: print("Sin fecha (agrégala a mano en fotos.json):\n  " + "\n  ".join(sin_fecha))
    if saltadas: print("Fotos HEIC saltadas; instala pillow-heif:\n  pip3 install pillow-heif")
    sin_lugar = [k for k, v in salida.items() if k in ubic and not v.get("lugar")]
    if sin_lugar: print(f"{len(sin_lugar)} fotos tienen GPS pero no nombre de lugar; complétalo en fotos.json (\"lugar\").")

if __name__ == "__main__":
    main()
