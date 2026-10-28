#!/usr/bin/env python3
"""Importa notas de Apple Notas al cuaderno (materiales/cuaderno/), tal cual, con su fecha y hora.

Uso (en la Mac, desde la carpeta del libro):
  osascript -l JavaScript herramientas/exportar_notas.js "Ágape" | python3 herramientas/importar_notas.py --autor Greg

- Solo lee la carpeta de Notas que le digas. No toca nada más.
- Las notas ya importadas (mismo id) se saltan; se puede correr las veces que haga falta.
- El texto se guarda sin corregir. Las notas con contraseña no se pueden leer y se saltan.
"""
import sys, json, re, html, argparse, unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CUAD = RAIZ / "materiales" / "cuaderno"
INDICE = CUAD / "INDICE.md"

def a_texto(h):
    h = re.sub(r"(?i)<br\s*/?>", "\n", h)
    h = re.sub(r"(?i)</(div|p|h\d|li|tr)>", "\n", h)
    h = re.sub(r"(?i)<li[^>]*>", "- ", h)
    h = re.sub(r"(?i)<img[^>]*>", "[imagen]", h)
    h = re.sub(r"<[^>]+>", "", h)
    h = html.unescape(h).replace("\xa0", " ")
    t = "\n".join(l.rstrip() for l in h.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", t).strip()

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return (re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40].strip("-")) or "nota"

def existentes():
    ids, por_fecha = {}, {}
    for p in CUAD.glob("20*.md"):
        t = p.read_text(encoding="utf-8")
        m = re.search(r"^id_notas:\s*(.+)$", t, re.M)
        if m: ids[m.group(1).strip()] = p
        f = re.search(r"^fecha:\s*(\S+)", t, re.M); a = re.search(r"^autor:\s*(\S+)", t, re.M)
        if f and a and not m: por_fecha.setdefault((f.group(1), a.group(1).lower()), []).append(p)
    return ids, por_fecha

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--autor", required=True, help="Greg o Nohemi")
    args = ap.parse_args()
    autor = args.autor.strip().capitalize()
    datos = json.load(sys.stdin)
    ids, por_fecha = existentes()
    nuevas, filas, avisos = 0, [], []
    for n in datos["notas"]:
        if n["id"] in ids: continue
        fecha, hora = n["creada"].split(" ")
        texto = a_texto(n["html"])
        titulo = (n["titulo"] or texto.split("\n", 1)[0] or "Nota").strip()[:80]
        nombre = f"{fecha}-{autor.lower()}-{slug(titulo)}.md"
        destino = CUAD / nombre; k = 2
        while destino.exists(): destino = CUAD / nombre.replace(".md", f"-{k}.md"); k += 1
        for p in por_fecha.get((fecha, autor.lower()), []):
            avisos.append(f"  posible duplicado: {destino.name} y {p.name} (misma fecha y autor)")
        destino.write_text(f"""---
fecha: {fecha}
hora: {hora}
autor: {autor}
tipo: nota
origen: Apple Notas ({datos.get("carpeta", "")})
id_notas: {n["id"]}
modificada: {n["modificada"]}
capitulos: []
uso:
estado: importada
---

# {titulo}

Nota de {autor} en Apple Notas, creada el {fecha} a las {hora}. Texto original, sin editar.

## Original

{texto}

## Para el libro

- 
""", encoding="utf-8")
        filas.append(f"| {fecha} | {autor} | `{destino.name}` | — | — | importada |")
        nuevas += 1
    if filas and INDICE.exists():
        lineas = INDICE.read_text(encoding="utf-8").split("\n")
        ult = max(i for i, l in enumerate(lineas) if l.startswith("| 20"))
        lineas[ult + 1:ult + 1] = filas
        INDICE.write_text("\n".join(lineas), encoding="utf-8")
    print(f"{nuevas} notas nuevas importadas en materiales/cuaderno/ ({len(datos['notas']) - nuevas} ya estaban).")
    if datos.get("bloqueadas"): print(f"{datos['bloqueadas']} notas con contraseña no se pudieron leer.")
    if avisos: print("Revisar:"); print("\n".join(avisos))

if __name__ == "__main__":
    main()
