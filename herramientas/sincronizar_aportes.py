#!/usr/bin/env python3
"""Sube lo que escribió el narrador (Claude) y baja los aportes de Supabase (recuerdos, fotos, escaneos) a .privado/aportes/ para que Claude los procese.

Uso (en la Mac, desde la carpeta del libro):
  python3 herramientas/sincronizar_aportes.py

Necesita .privado/supabase.env con:
  SUPABASE_URL=https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY=eyJ...   (la "service_role key": NUNCA en config.js ni en git)

Si existen .privado/aportes/salida/estaciones.json o narraciones.json (las escribe Claude en sus pasadas
profundas), primero los sube y los mueve a salida/publicado-<fecha>/.

Sin dependencias. No borra nada: los archivos ya bajados no se vuelven a bajar.
Cada persona queda en su propia carpeta. Lo de Nohemi está sellado hasta la revelación:
no abras su carpeta (Claude la procesa y no te cuenta lo que dice hasta que los dos revelen).
"""
import json, os, re, sys, urllib.request, urllib.parse, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PRIV = RAIZ / ".privado"
DEST = PRIV / "aportes"

def env():
    f = PRIV / "supabase.env"
    if not f.exists(): sys.exit("Falta .privado/supabase.env (ver herramientas/APORTES.md).")
    d = {}
    for l in f.read_text(encoding="utf-8").splitlines():
        if "=" in l and not l.strip().startswith("#"):
            k, v = l.split("=", 1); d[k.strip()] = v.strip().strip('"')
    if not d.get("SUPABASE_URL") or not d.get("SUPABASE_SERVICE_KEY"): sys.exit("Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en .privado/supabase.env")
    return d["SUPABASE_URL"].rstrip("/"), d["SUPABASE_SERVICE_KEY"]

URL, KEY = env()
H = {"apikey": KEY, "Authorization": "Bearer " + KEY}

def get(path):
    req = urllib.request.Request(URL + path, headers=H)
    with urllib.request.urlopen(req, timeout=60) as r: return r.read()

def enviar(path, filas):
    data = json.dumps(filas).encode("utf-8")
    req = urllib.request.Request(URL + path, data=data, method="POST", headers={**H, "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal"})
    with urllib.request.urlopen(req, timeout=60) as r: return r.status

def subir_narrador():
    sal = DEST / "salida"
    hechos = []
    for nombre, tabla in (("estaciones.json", "estaciones"), ("narraciones.json", "narraciones")):
        f = sal / nombre
        if not f.exists(): continue
        filas = json.loads(f.read_text(encoding="utf-8"))
        if filas: enviar(f"/rest/v1/{tabla}", filas)
        hechos.append((f, len(filas)))
    if hechos:
        import datetime
        dest = sal / ("publicado-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")); dest.mkdir(parents=True, exist_ok=True)
        for f, n in hechos:
            f.rename(dest / f.name); print(f"Narrador: {n} filas de {f.stem} publicadas.")

def slug(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "persona"

def fecha(r):
    s = str(r["anio"])
    if r.get("mes"): s += "-%02d" % r["mes"]
    if r.get("dia"): s += "-%02d" % r["dia"]
    if r.get("hora"): s += " " + r["hora"][:5]
    return s + (" (aprox.)" if r.get("aproximado") else "")

def main():
    subir_narrador()
    perfiles = json.loads(get("/rest/v1/perfiles?select=*"))
    try: recs = json.loads(get("/rest/v1/recuerdos?select=*,archivos(*),narraciones(*)&order=anio,mes.nullsfirst,dia.nullsfirst"))
    except Exception: recs = json.loads(get("/rest/v1/recuerdos?select=*,archivos(*)&order=anio,mes.nullsfirst,dia.nullsfirst"))
    try: ests = json.loads(get("/rest/v1/estaciones?select=*&order=desde"))
    except Exception: ests = []
    estado = {"revelado": bool(json.loads(get("/rest/v1/revelacion?select=fecha")))}
    por = {p["id"]: p for p in perfiles}
    DEST.mkdir(parents=True, exist_ok=True)
    nuevos = 0; resumen = []
    for p in perfiles:
        carpeta = DEST / f'{p["rol"]}-{slug(p["nombre"])}'
        (carpeta / "archivos").mkdir(parents=True, exist_ok=True)
        mios = [r for r in recs if r["autor"] == p["id"]]
        for r in mios:
            for a in r.get("archivos") or []:
                destino = carpeta / "archivos" / (r["id"][:8] + "-" + Path(a["ruta"]).name)
                a["local"] = str(destino.relative_to(DEST))
                if destino.exists(): continue
                ruta = urllib.parse.quote(a["ruta"])
                try: datos = get("/storage/v1/object/authenticated/aportes/" + ruta)
                except Exception: datos = get("/storage/v1/object/aportes/" + ruta)
                destino.write_bytes(datos); nuevos += 1
        (carpeta / "recuerdos.json").write_text(json.dumps(mios, ensure_ascii=False, indent=2), encoding="utf-8")
        sus_est = [e for e in ests if e["autor"] == p["id"]]
        (carpeta / "estaciones.json").write_text(json.dumps(sus_est, ensure_ascii=False, indent=2), encoding="utf-8")
        md = [f'# {p["nombre"]} ({p["rol"]})', "", f"{len(mios)} recuerdos.", ""]
        for r in mios:
            md += [f'## {fecha(r)} · {r.get("titulo") or "(sin título)"}', f'Etapa: {r["etapa"]}' + (f' · Lugar: {r["lugar"]}' if r.get("lugar") else ""), ""]
            if r.get("pregunta"): md += [f'> {r["pregunta"]}', ""]
            if r.get("texto"): md += [r["texto"], ""]
            n = r.get("narraciones")
            n = n[0] if isinstance(n, list) and n else n
            if n: md += [f'*Narrador (temperatura {n.get("temperatura")}):* {n.get("texto")}', ""]
            for a in r.get("archivos") or []:
                extra = (" · tomada " + a["tomada"][:16]) if a.get("tomada") else ""
                md.append(f'- archivo: {a.get("local")}{extra}')
            md.append("")
        (carpeta / "recuerdos.md").write_text("\n".join(md), encoding="utf-8")
        resumen.append(f'  {p["nombre"]} ({p["rol"]}): {len(mios)} recuerdos' + (" · listo/a para revelar" if p.get("listo_para_revelar") else ""))
    (DEST / "estado.json").write_text(json.dumps({"perfiles": [{k: p[k] for k in ("nombre", "rol", "listo_para_revelar")} for p in perfiles], **estado}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Aportes sincronizados en .privado/aportes/" + (" (las líneas ya se revelaron)" if estado["revelado"] else " (selladas)"))
    print("\n".join(resumen))
    print(f"{nuevos} archivos nuevos bajados.")

if __name__ == "__main__":
    main()
