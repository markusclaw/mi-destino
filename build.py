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


# ---------- línea del tiempo (archivo) ----------
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

def frontmatter(txt):
    m = re.match(r"^---\n(.*?)\n---\n", txt, re.S); meta = {}
    if m:
        for l in m.group(1).splitlines():
            if ":" in l:
                k, v = l.split(":", 1); meta[k.strip()] = v.strip().strip('"')
    return meta

def parse_fecha(s):
    m = re.match(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", s or "")
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)) if m else None

def h24(h):
    m = re.match(r"(\d{1,2}):(\d{2})\s*([AaPp])?", h or "")
    if not m: return ""
    hh, mm = int(m.group(1)), m.group(2)
    if m.group(3):
        pm = m.group(3).lower() == "p"
        hh = (hh % 12) + (12 if pm else 0)
    return f"{hh:02d}:{mm}"

def hora_es(h):
    if not h: return ""
    hh, mm = int(h[:2]), h[3:5]
    return f"{(hh % 12) or 12}:{mm} " + ("a. m." if hh < 12 else "p. m.")

def recolectar():
    items = []
    for p in sorted((RAIZ / "materiales" / "cuaderno").glob("20*.md")):
        txt = p.read_text(encoding="utf-8"); meta = frontmatter(txt)
        f = parse_fecha(meta.get("fecha"))
        if not f: continue
        h1 = re.search(r"^# (.+)$", txt, re.M); titulo = h1.group(1) if h1 else p.stem
        hora = h24(meta.get("hora") or (re.search(r"\d{1,2}:\d{2}\s*[AP]M", titulo) or [""])[0])
        titulo = re.split(r"\s+—\s+", titulo)[0]
        caps = re.findall(r"\d+", meta.get("capitulos", ""))
        items.append({"fecha": f, "hora": hora, "autor": voz_codigo(meta.get("autor", "")), "titulo": titulo,
                      "cap": caps[0] if caps else None, "foto": None, "lugar": meta.get("lugar", "")})
    fj = RAIZ / "materiales" / "fotos" / "fotos.json"
    if fj.exists():
        for ruta, d in json.loads(fj.read_text(encoding="utf-8")).items():
            f = parse_fecha(d.get("fecha"))
            if not f: continue
            q = (d.get("quien") or "").lower()
            items.append({"fecha": f, "hora": h24(d.get("hora", "")), "autor": "n" if q.startswith("noh") else "g" if q.startswith("greg") else "ng",
                          "titulo": d.get("pie", ""), "cap": str(d.get("capitulo") or "") or None, "foto": d.get("web") or ruta, "lugar": d.get("lugar", "")})
    items.sort(key=lambda x: (x["fecha"], x["hora"]))
    return items

def item_linea(it):
    y, mo, d = it["fecha"]
    cuando = ((f"{d} " if d else "") + (MESES[mo - 1] if mo else "")).strip()
    if it["hora"]: cuando += f", {hora_es(it['hora'])}"
    img = f'<img src="{esc(it["foto"])}" alt="" loading="lazy">' if it["foto"] else ""
    que = f'<span class="que">{esc(it["titulo"])}</span>' if it["titulo"] else ""
    lugar = f'<span class="lugar">{esc(it["lugar"])}</span>' if it["lugar"] else ""
    cuerpo = f'<span class="cuando">{esc(cuando)}</span>{img}{que}{lugar}'
    if it["cap"]: return f'<li><button type="button" data-ir="cap{it["cap"]}">{cuerpo}</button></li>'
    return f'<li><div>{cuerpo}</div></li>'

def pagina_linea():
    items = recolectar()
    if not items: return ""
    anios = {}
    for it in items: anios.setdefault(it["fecha"][0], []).append(it)
    vacio = '<li class="nada">—</li>'
    bloques = []
    for y in sorted(anios):
        col = {"n": [], "g": [], "ng": []}
        for it in anios[y]: col[it["autor"]].append(item_linea(it))
        ella = "".join(col["n"]) or vacio; el = "".join(col["g"]) or vacio
        juntos = f'<ol class="juntos">{"".join(col["ng"])}</ol>' if col["ng"] else ""
        bloques.append(f'<section class="anio"><h3>{y}</h3><div class="cols"><ol class="ella">{ella}</ol><ol class="el">{el}</ol></div>{juntos}</section>')
    return f'''<section class="pg linea" data-id="linea" data-titulo="La línea del tiempo" data-grupo="" data-voz="ng"><div class="wrap ancho">
  <p class="k">Archivo</p><h2>La línea del tiempo</h2>
  <p class="lead-linea">Cada nota, carta y foto con fecha, en su lugar. A la izquierda ella, a la derecha él: dónde estaba cada uno mientras el otro vivía lo suyo.</p>
  <div class="cab-cols"><span><i class="vn"></i>Ella</span><span><i class="vg"></i>Él</span></div>
  {"".join(bloques)}
</div></section>'''

def main():
    paginas = []
    # portada
    paginas.append(f'''<section class="pg portada" data-id="portada" data-titulo="Portada" data-grupo="">
  <div class="in">
    <p class="autores">{esc(cfg["autores"])}</p>
    <h1>{esc(cfg["titulo"])}</h1>
    <p class="subtitulo">{esc(cfg["subtitulo"])}</p>
    <svg class="caminos" viewBox="0 0 240 80" aria-hidden="true"><path class="n" pathLength="1" d="M2 10 C 70 10, 100 40, 150 40"/><path class="g" pathLength="1" d="M2 70 C 70 70, 100 40, 150 40"/><path class="u" pathLength="1" d="M150 40 L 238 40"/><circle cx="150" cy="40" r="2.6"/></svg>
    <div class="meta"><button class="btn" type="button" data-ir="prologo">Empezar a leer</button><button class="btn sec" type="button" id="continuar" hidden></button></div>
  </div>
</section>''')
    # definición
    df = cfg.get("definicion")
    if df:
        acep = "".join(f"<li>{esc(a)}</li>" for a in df["acepciones"])
        citas = "".join(f'<p class="v">{esc(c["texto"])}<cite>{esc(c["ref"])}</cite></p>' for c in df["citas"])
        paginas.append(f'''<section class="pg centrada definicion" data-id="definicion" data-titulo="Ágape: la palabra" data-grupo=""><div class="wrap"><div class="entrada">
  <h2>{esc(df["palabra"])}</h2>
  <p class="pron">{esc(df["silabas"])} <span>{esc(df["categoria"])}</span></p>
  <p class="origen">Del griego <span lang="grc" class="g">{esc(df["griego"])}</span> <i>{esc(df["griego_lat"])}</i>, «{esc(df["griego_sentido"])}».</p>
  <ol>{acep}</ol>
  <div class="hebreo"><p class="h"><span lang="he" dir="rtl">{esc(df["hebreo"])}</span> <i>{esc(df["hebreo_lat"])}</i> <span class="et">en hebreo</span></p><p>{esc(df["nota_hebreo"])}</p></div>
  <div class="citas">{citas}</div>
</div></div></section>''')
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
    linea = pagina_linea()
    if linea: paginas.append(linea)
    f = cfg["fin"]
    paginas.append(f'''<section class="pg centrada fin" data-id="fin" data-titulo="Fin" data-grupo=""><div class="wrap">
  <p class="titulo">{esc(cfg["titulo"])}</p><p class="subtitulo">{esc(cfg["subtitulo"])}</p><p>{esc(f["texto"])}</p>
  <div class="leyenda"><span><span class="voces"><i class="vn"></i></span>Nohemi</span><span><span class="voces"><i class="vg"></i></span>Greg</span><span>{esc(e["cita"])}</span></div>
  <div class="acciones"><button type="button" data-ir="portada">Volver a la portada</button><button type="button" data-ir="indice">Ir al índice</button></div>
  <p class="pie">{esc(f["pie"])}</p></div></section>''')
    plantilla = (RAIZ / "plantilla.html").read_text(encoding="utf-8")
    salida = (plantilla.replace("{{TITULO}}", esc(cfg["titulo"] + " · " + cfg["subtitulo"])).replace("{{CORTO}}", esc(cfg["nombre_corto"])).replace("{{PAGINAS}}", "\n\n".join(paginas)))
    (RAIZ / "index.html").write_text(salida, encoding="utf-8")
    n = len(paginas); escritos = sum(1 for p in paginas if 'class="pg cap"' in p and 'class="vacio">Este capítulo' not in p)
    print(f"index.html generado: {n} páginas, {escritos} capítulos con texto.")

if __name__ == "__main__":
    main()
