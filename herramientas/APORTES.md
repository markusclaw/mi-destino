# Aportes: cada quien escribe su lado, y el narrador se lo devuelve

La página `aportar/` es donde Nohemi, Greg y los invitados escriben momentos y suben fotos, escaneos de cartas y capturas.
Cada momento lo lee **el narrador** (Claude): le devuelve a su autor una narración breve en segunda persona,
lo ubica en una estación de su vida, le pone temperatura, transcribe las cartas de las fotos y le hace una pregunta
para el siguiente momento. La voz del narrador está en `herramientas/NARRADOR.md`.
Cada persona ve solo lo suyo. Cuando Nohemi y Greg marcan los dos «Estoy listo/a para revelar», sus dos líneas se abren
para los dos, para siempre, en «Nuestra historia». Los invitados (testigos) solo ven lo que ellos mismos escriben.

Lo protege la base de datos (Row Level Security de Supabase), no solo la página.
Aun así, quien administra el proyecto (Greg) podría técnicamente mirar: el sello es por diseño y por acuerdo.

## Instalar (una vez, unos 20 minutos)

1. **Proyecto.** En supabase.com → New project → nombre `agape`. Guarda la contraseña de la base de datos en tu administrador de contraseñas.
2. **Tablas y reglas.** SQL Editor → New query → pega todo `aportar/supabase.sql` → **Run**.
   Después, en otra query, pega `aportar/supabase-narrador.sql` → **Run**.
3. **Invitados.** En SQL Editor, con los correos reales:
   ```sql
   insert into public.invitados (email, nombre, rol) values
     ('correo-de-nohemi@ejemplo.com', 'Nohemi', 'nohemi'),
     ('correo-de-greg@ejemplo.com',   'Greg',   'greg');
   -- testigos, cuando quieran:
   -- insert into public.invitados values ('peter@ejemplo.com', 'Peter', 'testigo');
   ```
4. **Que nadie más se registre.** Authentication → Sign In / Providers → desactiva **Allow new users to sign up**. Email debe quedar activado.
5. **La página.** Project Settings → API (o Data API): copia **Project URL** y la **anon public** key a `aportar/config.js`.
   La anon key está hecha para ir en una página pública; las reglas de la base de datos protegen los datos.
6. **Publicarla.** Cloudflare Pages → Create → conectar el repositorio `mi-destino` → Build command: *(vacío)* → Build output directory: `aportar` → Deploy.
   Te da una dirección tipo `https://agape-aportes.pages.dev` (o pon un dominio tuyo).
7. **Dirección de regreso del correo.** Supabase → Authentication → URL Configuration → **Site URL** = la dirección del paso 6. Agrégala también en **Redirect URLs**.
8. **Invitar.** Authentication → Users → **Invite user** → el correo de Nohemi, el tuyo, y cada testigo.
   Al aceptar, su perfil se crea solo con el nombre y el rol del paso 3. Desde entonces entran con su correo en la página (llega un enlace, sin contraseña).
9. **El narrador al instante.**
   - Supabase → Edge Functions → **Secrets**: agrega `ANTHROPIC_API_KEY` con tu llave de la API de Anthropic
     (la misma clase de llave que usas en Witness Archive). Opcional: `NARRADOR_MODELO` (por defecto `claude-sonnet-5-5`).
   - Edge Functions → **Deploy a new function** → **Via Editor** → nombre `narrar` → pega `aportar/funciones/narrar/index.ts` → Deploy.
     (O con la terminal: `supabase functions deploy narrar`, copiando la carpeta a `supabase/functions/narrar/`.)
   - Costo: unos centavos por momento. Si la función no está, la página sigue funcionando: el momento queda guardado
     y el narrador lo lee en la siguiente sincronización con Claude.
10. **La llave de Claude.** Project Settings → API → copia la **service_role** key y guárdala en `.privado/supabase.env`:
   ```
   SUPABASE_URL=https://xxxx.supabase.co
   SUPABASE_SERVICE_KEY=eyJ...
   ```
   Esa llave lo abre todo: nunca en `config.js`, nunca en git (`.privado/` no se sube).

## Usar

- Cada quien abre la página, escribe recuerdos (con año aunque sea aproximado), responde preguntas y sube archivos.
  Si una foto trae fecha, la página la toma sola.
- Para que Claude procese lo nuevo:
  ```bash
  cd ~/Documents/mi-destino
  python3 herramientas/sincronizar_aportes.py
  ```
  Primero sube lo que Claude dejó en `.privado/aportes/salida/` (narraciones de estaciones completas, correcciones),
  y después baja todo a `.privado/aportes/<persona>/`. Dile a Claude «sincronicé».
  En esas pasadas profundas Claude lee la línea completa de cada quien, reescribe las estaciones con más contexto,
  transcribe lo que el narrador al instante no pudo (fotos HEIC, PDF) y prepara borradores de capítulos.
- **El sello:** la carpeta de Nohemi queda en tu Mac. No la abras; Claude tampoco te cuenta lo que dice hasta que los dos revelen.

## Si algo falla

- *«El narrador leerá tu momento pronto» y nunca aparece*: la función `narrar` no está o le falta `ANTHROPIC_API_KEY`.
  Supabase → Edge Functions → narrar → Logs dice por qué.

- *«Ese correo no está invitado»*: falta en `invitados` o no se le mandó **Invite user**.
- *Entró pero dice que no está en la lista*: se creó el usuario antes de agregarlo a `invitados`. Arreglo:
  ```sql
  insert into public.perfiles (id, email, nombre, rol)
  select u.id, u.email, i.nombre, i.rol from auth.users u join public.invitados i on lower(i.email) = lower(u.email)
  on conflict (id) do nothing;
  ```
- *El enlace del correo lleva a otra página*: revisa el paso 7.
