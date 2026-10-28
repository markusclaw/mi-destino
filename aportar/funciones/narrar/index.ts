// Ágape · función "narrar"
// Lee un momento recién escrito y le devuelve a su autor una narración, una temperatura,
// su estación de vida, la transcripción de sus imágenes y una pregunta para seguir.
// Solo lee momentos del mismo autor: nunca ve lo que escribió la otra persona.
//
// Secretos necesarios (Supabase → Edge Functions → Secrets):
//   ANTHROPIC_API_KEY   tu llave de la API de Anthropic
//   NARRADOR_MODELO     opcional; por defecto claude-sonnet-5-5
// SUPABASE_URL, SUPABASE_ANON_KEY y SUPABASE_SERVICE_ROLE_KEY los pone Supabase solo.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
import { encodeBase64 } from "https://deno.land/std@0.224.0/encoding/base64.ts";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (b: unknown, s = 200) => new Response(JSON.stringify(b), { status: s, headers: { ...CORS, "Content-Type": "application/json" } });
const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const ETAPAS: Record<string, string> = { antes: "Antes de conocernos", celula: "La célula", juntos: "Juntos" };

const SISTEMA = `Eres el narrador de "Ágape · Dos caminos, un destino", un libro de legado escrito a dos voces por Nohemi y Greg.
Cada persona escribe su lado de la historia sin ver lo que escribe la otra, hasta el día en que los dos deciden revelar.
Tu trabajo: leer el momento que esta persona acaba de entregar y devolverle una narración que lo sitúe en su historia.

Voz: hablas de tú, en español, cálido y sobrio, como un narrador de documental que conoce bien a la persona.
No eres consejero ni predicador: cuentas, sitúas, conectas.

Reglas:
- Usa solo lo que la persona escribió (este momento y sus momentos anteriores). No inventes hechos, nombres ni lugares. Si algo no está claro, no lo afirmes.
- No corrijas ni embellezcas su texto: su voz queda intacta, tu narración va aparte. Adáptate a su registro.
- Nombra lo que se siente sin diagnosticar: nada de etiquetas clínicas.
- La fe es el marco de esta historia; nómbrala cuando la persona la nombra, sin predicar.
- Nunca menciones ni supongas lo que escribió la otra persona del libro. Solo conoces a esta persona.
- Dolor del pasado: acompáñalo con respeto. Si el momento parece describir una crisis ACTUAL (por ejemplo, querer hacerse daño hoy), no narres: en "narracion" responde breve y con calidez, anima a hablar hoy con alguien de confianza o con una línea de ayuda, y pon temperatura 1.

Devuelve SOLO un objeto JSON, sin texto alrededor, con esta forma:
{
  "narracion": "2 a 4 oraciones, en segunda persona",
  "temperatura": 1-5 (1 dolor, 3 neutral u ocupado, 5 gozo o paz), según lo escrito,
  "temas": ["2 a 4 palabras clave"],
  "pregunta": "una sola pregunta concreta que invite a escribir el siguiente momento: una escena, un detalle, una persona",
  "transcripcion": "texto literal que aparezca en las imágenes (cartas, notas, capturas), o null",
  "estacion": {
    "id": "id de una estación existente si el momento cae en ella, o null para proponer una nueva",
    "titulo": "nombre evocador de 2 a 5 palabras para la temporada de vida",
    "desde": año en que empieza,
    "hasta": año en que termina o null si sigue abierta,
    "narracion": "3 a 5 oraciones sobre esa temporada si es nueva o si este momento cambia su sentido; si no, null"
  }
}`;

function fecha(r: any) {
  let s = "";
  if (r.dia && r.mes) s = `${r.dia} de ${MESES[r.mes - 1]} de ${r.anio}`;
  else if (r.mes) s = `${MESES[r.mes - 1]} de ${r.anio}`;
  else s = String(r.anio);
  if (r.hora) s += `, ${String(r.hora).slice(0, 5)}`;
  return s + (r.aproximado ? " (aprox.)" : "");
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });
  try {
    const { recuerdo } = await req.json();
    if (!recuerdo) return json({ error: "falta recuerdo" }, 400);
    const URL = Deno.env.get("SUPABASE_URL")!, ANON = Deno.env.get("SUPABASE_ANON_KEY")!;
    const SERVICIO = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, LLAVE = Deno.env.get("ANTHROPIC_API_KEY");
    const MODELO = Deno.env.get("NARRADOR_MODELO") || "claude-sonnet-5-5";
    if (!LLAVE) return json({ error: "falta ANTHROPIC_API_KEY" }, 503);

    // ¿quién llama?
    const comoUsuario = createClient(URL, ANON, { global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } } });
    const { data: { user } } = await comoUsuario.auth.getUser();
    if (!user) return json({ error: "no autorizado" }, 401);

    const db = createClient(URL, SERVICIO);
    const { data: rec } = await db.from("recuerdos").select("*, archivos(*)").eq("id", recuerdo).single();
    if (!rec || rec.autor !== user.id) return json({ error: "no encontrado" }, 404);
    const { data: perfil } = await db.from("perfiles").select("nombre, rol").eq("id", user.id).single();
    const { data: previos } = await db.from("recuerdos")
      .select("id, anio, mes, dia, hora, aproximado, etapa, lugar, titulo, texto, narraciones(texto, temperatura)")
      .eq("autor", user.id).neq("id", recuerdo)
      .order("anio").order("mes", { nullsFirst: true }).order("dia", { nullsFirst: true }).limit(80);
    const { data: estaciones } = await db.from("estaciones").select("id, titulo, desde, hasta, narracion").eq("autor", user.id).order("desde");

    // imágenes (JPEG, PNG, GIF, WebP; hasta 4)
    const imagenes: unknown[] = [];
    for (const a of (rec.archivos ?? [])) {
      if (imagenes.length >= 4) break;
      if (!/^image\/(jpeg|png|gif|webp)$/.test(a.tipo ?? "")) continue;
      const { data: blob } = await db.storage.from("aportes").download(a.ruta);
      if (!blob || blob.size > 4_500_000) continue;
      imagenes.push({ type: "image", source: { type: "base64", media_type: a.tipo, data: encodeBase64(new Uint8Array(await blob.arrayBuffer())) } });
    }

    const lista = (previos ?? []).map((p: any) => ({ ...p, narraciones: Array.isArray(p.narraciones) ? p.narraciones[0] : p.narraciones })).map((p: any) =>
      `- ${fecha(p)} · ${ETAPAS[p.etapa] ?? p.etapa}${p.lugar ? " · " + p.lugar : ""}${p.titulo ? " · «" + p.titulo + "»" : ""}\n  ${(p.texto ?? "").replace(/\s+/g, " ").slice(0, 400)}` +
      (p.narraciones?.texto ? `\n  (narrado: ${p.narraciones.texto})` : "")).join("\n");
    const ests = (estaciones ?? []).map((e: any) => `- id ${e.id}: «${e.titulo}» (${e.desde}–${e.hasta ?? "…"})${e.narracion ? ": " + e.narracion : ""}`).join("\n");
    const texto = `Autor: ${perfil?.nombre} (${perfil?.rol === "nohemi" ? "Ella" : perfil?.rol === "greg" ? "Él" : "testigo"})

Momentos anteriores de esta persona (en orden):
${lista || "(ninguno todavía: este es el primero)"}

Estaciones que ya existen en su línea:
${ests || "(ninguna todavía)"}

MOMENTO NUEVO
Fecha: ${fecha(rec)}
Parte de la historia: ${ETAPAS[rec.etapa] ?? rec.etapa}
Lugar: ${rec.lugar ?? "(no dijo)"}
Título: ${rec.titulo ?? "(sin título)"}
${rec.pregunta ? "Respondía a la pregunta: " + rec.pregunta + "\n" : ""}Texto:
${rec.texto ?? "(sin texto; solo archivos)"}
${imagenes.length ? `\nAdjuntó ${imagenes.length} imagen(es), arriba.` : ""}`;

    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "x-api-key": LLAVE, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({ model: MODELO, max_tokens: 1500, system: SISTEMA, messages: [{ role: "user", content: [...imagenes, { type: "text", text: texto }] }] }),
    });
    if (!r.ok) return json({ error: "narrador no disponible", detalle: await r.text() }, 502);
    const salida = await r.json();
    const crudo = (salida.content ?? []).filter((c: any) => c.type === "text").map((c: any) => c.text).join("");
    const m = crudo.match(/\{[\s\S]*\}/);
    if (!m) return json({ error: "respuesta sin formato" }, 502);
    const n = JSON.parse(m[0]);

    // estación: existente o nueva
    let estacion: string | null = null;
    const e = n.estacion;
    if (e?.id && (estaciones ?? []).some((x: any) => x.id === e.id)) {
      estacion = e.id;
      const cambios: Record<string, unknown> = { actualizado: new Date().toISOString() };
      if (e.narracion) cambios.narracion = e.narracion;
      if (e.hasta !== undefined) cambios.hasta = e.hasta;
      if (e.titulo) cambios.titulo = e.titulo;
      await db.from("estaciones").update(cambios).eq("id", e.id).eq("autor", user.id);
    } else if (e?.titulo && e?.desde) {
      const { data: nueva } = await db.from("estaciones")
        .insert({ autor: user.id, titulo: e.titulo, desde: e.desde, hasta: e.hasta ?? null, narracion: e.narracion ?? null })
        .select("id").single();
      estacion = nueva?.id ?? null;
    }

    const fila = {
      recuerdo, autor: user.id, texto: String(n.narracion ?? "").trim(),
      transcripcion: n.transcripcion || null,
      temperatura: Math.min(5, Math.max(1, Math.round(Number(n.temperatura) || 3))),
      temas: Array.isArray(n.temas) ? n.temas.slice(0, 6).map(String) : null,
      pregunta: n.pregunta || null, estacion, modelo: MODELO, creado: new Date().toISOString(),
    };
    if (!fila.texto) return json({ error: "narración vacía" }, 502);
    await db.from("narraciones").upsert(fila);
    return json({ ok: true, narracion: fila });
  } catch (err) {
    return json({ error: String(err) }, 500);
  }
});
