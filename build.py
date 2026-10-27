#!/usr/bin/env python3
"""Genera index.html a partir de manuscrito/ y libro.json. Sin dependencias.
Uso:  python3 build.py
"""
import json, re, html, os, sys
from pathlib import Path

RAIZ = Path(__file__).parent
MAN = RAIZ / "manuscrito"
cfg = json.loads((RAIZ / "libro.json").read_text(encoding="utf-8"))

ESTADOS = {"idea": "Por escribir", "preguntas": "En escritura", "borrador": "Borrador", "revisado": "Revisado", "final": ""}
VOZ = {"nohemi": "n", "greg": "g", "ambos": "ng", "ambas": "ng", "nohemi y greg": "ng", "cada uno": "ng", "cada uno escribe la suya": "ng"}

def esc(t): return html.escape(t, quote=False)

def inline(t):
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\w)[_*](.+?)[_*](?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"~~(.+?)~~", r'<span class="tachado">\1</span>', t)
    t = re.sub(r"\[\[revisar\]\]", '<mark class="revisar">revisar</mark>', t)
    return t

def voz_codigo(v):
    v = (v or "").strip().lower()
    v = re.sub(r"\(.*?\)", "", v).strip()
    if "nohemi" in v and "greg" in v: return "ng"
    for k, c in VOZ.items():
        if v.startswith(k): return c
    if "nohemi" in v: return "n"
    if "greg" in v: return "g"
    return "ng"

def leer_capitulo(p: Path):
    txt = p.read_text(encoding="utf-8")
    lineas = txt.splitlines()
    cap = {"archivo": p, "titulo": "", "voz": "", "estado": "idea", "intro": "", "cuerpo": ""}
    for l in lineas:
        if l.startswith("# ") and not cap["titulo"]: cap["titulo"] = l[2:].strip()
        m = re.match(r"- \*\*Voz:\*\*\s*(.+)", l)
        if m: cap["voz"] = m.group(1).strip()
        m = re.match(r"- \*\*Estado:\*\*\s*(\w+)", l)
        if m: cap["estado"] = m.group(1).strip().lower()
    # intro: primer bloque de cita (> ...) antes de "## Borrador"
    pre = txt.split("## Borrador")[0]
    intro = [l[1:].strip() for l in pre.splitlines() if l.startswith(">")]
    cap["intro"] = " ".join(intro)
    # cuerpo: sección "## Borrador" hasta el siguiente "## "
    m = re.search(r"^## Borrador[^\n]*\n(.*?)(?=^## |\Z)", txt, re.S | re.M)
    cuerpo = m.group(1) if m else ""
    # quitar la línea guía por defecto
    cuerpo = re.sub(r"^_\(Escribe aquí.*?\)_\s*$", "", cuerpo, flags=re.M)
    cap["cuerpo"] = cuerpo.strip()
    return cap

def render_cuerpo(md):
    """Mini-markdown: párrafos, — Voz, ::: cuaderno, > citas, ### subtítulos, !! pregunta, [[pendiente: ...]]"""
    out, i = [], 0
    bloques = re.split(r"\n\s*\n", md.strip())
    for b in bloques:
        b = b.strip()
        if not b: continue
        if b.startswith("::: cuaderno"):
            cab, _, resto = b.partition("\n")
            partes = [x.strip() for x in cab[len("::: cuaderno"):].split("|")]
            autor = partes[0] if partes else ""
            fecha = partes[1] if len(partes) > 1 else ""
            nota = partes[2] if len(partes) > 2 else ""
            resto = resto.rsplit(":::", 1)[0].strip()
            v = voz_codigo(autor); color = "var(--greg)" if v == "g" else "var(--nohemi)"
            ps = "".join(f"<p>{inline(x.strip())}</p>" for x in re.split(r"\n\s*\n", resto) if x.strip())
            meta = f"<b>Del cuaderno de {esc(autor)}</b>" + (f"<span>{esc(fecha)}</span>" if fecha else "") + (f"<span>{esc(nota)}</span>" if nota else "")
            out.append(f'<aside class="cuaderno" style="--v:{color}"><p class="de">{meta}</p>{ps}</aside>')
            continue
        m = re.match(r"^[—-]\s*(Nohemi|Greg)\s*$", b)
        if m:
            v = m.group(1); color = "var(--greg)" if v == "Greg" else "var(--nohemi)"
            out.append(f'<p class="habla" style="--v:{color}">{v}</p>'); continue
        m = re.match(r"^\[\[pendiente:\s*(.+?)\]\]$", b, re.S)
        if m:
            out.append(f'<p class="vacio">{inline(m.group(1).strip())}</p>'); continue
        if b.startswith("### "):
            out.append(f"<h3>{inline(b[4:].strip())}</h3>"); continue
        if b.startswith("!! "):
            out.append(f'<p class="pregunta">{inline(b[3:].strip())}</p>'); continue
        if all(l.startswith(">") for l in b.splitlines()):
            q = " ".join(l[1:].strip() for l in b.splitlines())
            out.append(f'<blockquote class="cita">{inline(q)}</blockquote>'); continue
        if all(re.match(r"^[-*] ", l) for l in b.splitlines()):
            items = "".join(f"<li>{inline(l[2:].strip())}</li>" for l in b.splitlines())
            out.append(f"<ul>{items}</ul>"); continue
        out.append(f"<p>{inline(' '.join(l.strip() for l in b.splitlines()))}</p>")
    return "\n".join(out)

def autor_html(voz):
    v = voz_codigo(voz)
    av = {"n": '<span class="av n">N</span>', "g": '<span class="av g">G</span>'}
    if v == "ng": return f'<div class="autor"><span class="dos">{av["n"]}{av["g"]}</span>{esc(voz or "Nohemi y Greg")}</div>'
    nombre = "Nohemi" if v == "n" else "Greg"
    return f'<div class="autor">{av[v]}{esc(voz or nombre)}</div>'

def pagina_cap(cap, pid, kicker, num, grupo):
    estado = ESTADOS.get(cap["estado"], cap["estado"])
    cuerpo = render_cuerpo(cap["cuerpo"]) if cap["cuerpo"] else ""
    if not cuerpo:
        cuerpo = f'<p class="vacio">Este capítulo todavía se está escribiendo.' + (f'<small>{esc(cap["intro"])}</small>' if cap["intro"] else "") + "</p>"
    titulo_toc = cap["titulo"] if num else kicker
    attrs = f'data-id="{pid}" data-titulo="{esc(titulo_toc)}" data-grupo="{esc(grupo)}" data-voz="{voz_codigo(cap["voz"])}" data-estado="{esc(estado)}"'
    if num: attrs += f' data-num="{num}"'
    return f'''<article class="pg cap" {attrs}><div class="wrap">
  <p class="k">{esc(kicker)}</p><h2>{esc(cap["titulo"])}</h2>{autor_html(cap["voz"])}
  {cuerpo}
</div></article>'''

def pagina_parte(i, parte, caps):
    lista = "".join(f'<button type="button" data-ir="{c[0]}">{c[1]}. {esc(c[2])}</button>' for c in caps)
    return f'''<section class="pg centrada parte-abre" data-id="parte{i}" data-titulo="{esc(parte["ordinal"])}" data-sub="{esc(parte["titulo"])}" data-grupo="">
  <div class="wrap"><p class="k">{esc(parte["ordinal"])}</p><h2>{esc(parte["titulo"])}</h2><p>{esc(parte["descripcion"])}</p><div class="caps">{lista}</div></div>
</section>'''

def main():
    paginas = []
    # portada
    titulo_h1 = esc(cfg["titulo"]).replace(", ", ",<br>", 1)
    paginas.append(f'''<section class="pg portada" data-id="portada" data-titulo="Portada" data-grupo="">
  <div class="in">
    <p class="autores">{esc(cfg["autores"])}</p>
    <h1>{titulo_h1}</h1>
    <svg class="caminos" viewBox="0 0 240 80" aria-hidden="true"><path class="n" pathLength="1" d="M2 10 C 70 10, 100 40, 150 40"/><path class="g" pathLength="1" d="M2 70 C 70 70, 100 40, 150 40"/><path class="u" pathLength="1" d="M150 40 L 238 40"/><circle cx="150" cy="40" r="2.6"/></svg>
    <div class="meta"><button class="btn" type="button" data-ir="prologo">Empezar a leer</button><button class="btn sec" type="button" id="continuar" hidden></button></div>
  </div>
</section>''')
    # dedicatoria (si tiene texto)
    ded = leer_capitulo(MAN / "00-apertura/dedicatoria.md")
    if ded["cuerpo"]:
        paginas.append(f'<section class="pg centrada dedicatoria" data-id="dedicatoria" data-titulo="Dedicatoria" data-grupo=""><div class="wrap">{render_cuerpo(ded["cuerpo"])}</div></section>')
    e = cfg["epigrafe"]
    paginas.append(f'<section class="pg centrada epi" data-id="epigrafe" data-titulo="Epígrafe" data-grupo=""><div class="wrap"><blockquote>{esc(e["texto"])}</blockquote><cite>{esc(e["cita"])}</cite></div></section>')
    paginas.append('''<section class="pg sec toc" data-id="indice" data-titulo="Índice" data-grupo=""><div class="wrap">
  <h2>Índice</h2><p class="lead">Quién habla:<span class="voces"><i class="vn"></i></span>Nohemi<span class="voces"><i class="vg"></i></span>Greg</p><div id="toc-lista"></div></div></section>''')
    nota = leer_capitulo(MAN / "00-apertura/nota-al-lector.md")
    if nota["cuerpo"]:
        paginas.append(pagina_cap(nota, "nota", "Nota a quien lea esto", None, ""))
    pro = leer_capitulo(MAN / "00-apertura/prologo.md")
    paginas.append(pagina_cap(pro, "prologo", "Prólogo", None, ""))
    for i, parte in enumerate(cfg["partes"], 1):
        archivos = sorted((MAN / parte["carpeta"]).glob("[0-9][0-9]-*.md"))
        caps = []
        for a in archivos:
            num = int(a.name[:2]); cap = leer_capitulo(a); caps.append((f"cap{num}", num, cap["titulo"], cap))
        paginas.append(pagina_parte(i, parte, caps))
        for pid, num, _, cap in caps:
            paginas.append(pagina_cap(cap, pid, f"Capítulo {num}", num, parte["ordinal"]))
    epi = leer_capitulo(MAN / "05-cierre/epilogo.md")
    paginas.append(pagina_cap(epi, "epilogo", "Epílogo", None, ""))
    agr = leer_capitulo(MAN / "05-cierre/agradecimientos.md")
    if agr["cuerpo"]:
        paginas.append(pagina_cap(agr, "agradecimientos", "Agradecimientos", None, ""))
    f = cfg["fin"]
    paginas.append(f'''<section class="pg centrada fin" data-id="fin" data-titulo="Fin" data-grupo=""><div class="wrap">
  <p class="titulo">{esc(cfg["titulo"])}</p><p>{esc(f["texto"])}</p>
  <div class="leyenda"><span><span class="voces"><i class="vn"></i></span>Nohemi</span><span><span class="voces"><i class="vg"></i></span>Greg</span><span>{esc(e["cita"])}</span></div>
  <div class="acciones"><button type="button" data-ir="portada">Volver a la portada</button><button type="button" data-ir="indice">Ir al índice</button></div>
  <p class="pie">{esc(f["pie"])}</p></div></section>''')
    plantilla = (RAIZ / "plantilla.html").read_text(encoding="utf-8")
    salida = (plantilla.replace("{{TITULO}}", esc(cfg["titulo"])).replace("{{CORTO}}", esc(cfg["nombre_corto"])).replace("{{PAGINAS}}", "\n\n".join(paginas)))
    (RAIZ / "index.html").write_text(salida, encoding="utf-8")
    n = len(paginas); escritos = sum(1 for p in paginas if 'class="pg cap"' in p and 'class="vacio">Este capítulo' not in p)
    print(f"index.html generado: {n} páginas, {escritos} capítulos con texto.")

if __name__ == "__main__":
    main()
