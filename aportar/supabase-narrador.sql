-- Ágape · El narrador
-- Correr DESPUÉS de supabase.sql (SQL Editor → New query → pegar → Run).
-- Las narraciones y las estaciones solo las escribe el narrador (la función "narrar" y la sincronización de Claude).
-- Cada persona ve las suyas; después de la revelación, Nohemi y Greg ven las de los dos.

create table public.estaciones (
  id         uuid primary key default gen_random_uuid(),
  autor      uuid not null references public.perfiles(id) on delete cascade,
  titulo     text not null,
  desde      int  not null,
  hasta      int,
  narracion  text,
  creado     timestamptz not null default now(),
  actualizado timestamptz not null default now()
);
alter table public.estaciones enable row level security;

create table public.narraciones (
  recuerdo     uuid primary key references public.recuerdos(id) on delete cascade,
  autor        uuid not null references public.perfiles(id) on delete cascade,
  texto        text not null,
  transcripcion text,
  temperatura  smallint check (temperatura between 1 and 5),
  temas        text[],
  pregunta     text,
  estacion     uuid references public.estaciones(id) on delete set null,
  modelo       text,
  creado       timestamptz not null default now()
);
alter table public.narraciones enable row level security;

create policy "estaciones: ver"  on public.estaciones  for select to authenticated using (public.puedo_ver(autor));
create policy "narraciones: ver" on public.narraciones for select to authenticated using (public.puedo_ver(autor));
-- Sin reglas de escritura: nadie las escribe desde la página; solo el narrador con la llave de servicio.
