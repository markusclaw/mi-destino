-- Ágape · Aportes
-- Correr UNA vez en Supabase → SQL Editor → New query → pegar todo → Run.
-- Cada persona ve solo lo suyo. Cuando Nohemi y Greg marcan "listo/a", sus dos líneas se abren para los dos, para siempre.

-- 1. Quién está invitado (la llenas tú; la app no puede leerla)
create table public.invitados (
  email  text primary key,
  nombre text not null,
  rol    text not null check (rol in ('nohemi','greg','testigo'))
);
alter table public.invitados enable row level security;

-- 2. Perfiles: se crean solos cuando un invitado entra por primera vez
create table public.perfiles (
  id     uuid primary key references auth.users(id) on delete cascade,
  email  text not null,
  nombre text not null,
  rol    text not null check (rol in ('nohemi','greg','testigo')),
  listo_para_revelar boolean not null default false,
  creado timestamptz not null default now()
);
alter table public.perfiles enable row level security;

create or replace function public.crear_perfil() returns trigger
language plpgsql security definer set search_path = public as $$
declare i record;
begin
  select * into i from public.invitados where lower(email) = lower(new.email);
  if found then
    insert into public.perfiles (id, email, nombre, rol) values (new.id, new.email, i.nombre, i.rol)
    on conflict (id) do nothing;
  end if;
  return new;
end $$;

create trigger al_crear_usuario after insert on auth.users
for each row execute function public.crear_perfil();

-- 3. La revelación (una sola fila cuando ocurre; no se deshace)
create table public.revelacion (
  id    int primary key default 1 check (id = 1),
  fecha timestamptz not null default now()
);
alter table public.revelacion enable row level security;

-- 4. Recuerdos y archivos
create table public.recuerdos (
  id         uuid primary key default gen_random_uuid(),
  autor      uuid not null default auth.uid() references public.perfiles(id) on delete cascade,
  anio       int  not null check (anio between 1950 and 2100),
  mes        int  check (mes between 1 and 12),
  dia        int  check (dia between 1 and 31),
  hora       time,
  aproximado boolean not null default false,
  etapa      text not null default 'antes' check (etapa in ('antes','celula','juntos')),
  lugar      text,
  titulo     text,
  texto      text,
  pregunta   text,
  creado     timestamptz not null default now(),
  actualizado timestamptz not null default now()
);
alter table public.recuerdos enable row level security;

create table public.archivos (
  id       uuid primary key default gen_random_uuid(),
  recuerdo uuid not null references public.recuerdos(id) on delete cascade,
  autor    uuid not null default auth.uid() references public.perfiles(id) on delete cascade,
  ruta     text not null,
  nombre   text,
  tipo     text,
  tomada   timestamptz,
  lat      double precision,
  lon      double precision,
  creado   timestamptz not null default now()
);
alter table public.archivos enable row level security;

-- 5. Funciones auxiliares
create or replace function public.mi_rol() returns text
language sql stable security definer set search_path = public as $$
  select rol from public.perfiles where id = auth.uid()
$$;

create or replace function public.revelado() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.revelacion)
$$;

create or replace function public.es_pareja(uid uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.perfiles where id = uid and rol in ('nohemi','greg'))
$$;

-- puedo ver lo de esta persona: es mío, o ya se reveló y los dos somos la pareja
create or replace function public.puedo_ver(uid uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select uid = auth.uid()
      or (public.revelado() and public.mi_rol() in ('nohemi','greg') and public.es_pareja(uid))
$$;

create or replace function public.estado_revelacion() returns json
language sql stable security definer set search_path = public as $$
  select json_build_object(
    'yo',       coalesce((select listo_para_revelar from public.perfiles where id = auth.uid()), false),
    'otro',     coalesce((select bool_or(listo_para_revelar) from public.perfiles where rol in ('nohemi','greg') and id <> auth.uid()), false),
    'revelado', public.revelado(),
    'fecha',    (select fecha from public.revelacion)
  )
$$;

create or replace function public.marcar_listo(v boolean) returns json
language plpgsql security definer set search_path = public as $$
begin
  if public.mi_rol() not in ('nohemi','greg') then raise exception 'solo Nohemi y Greg'; end if;
  if public.revelado() then return public.estado_revelacion(); end if;
  update public.perfiles set listo_para_revelar = v where id = auth.uid();
  if (select count(*) from public.perfiles where rol in ('nohemi','greg') and listo_para_revelar) = 2 then
    insert into public.revelacion (id) values (1) on conflict do nothing;
  end if;
  return public.estado_revelacion();
end $$;

grant execute on function public.mi_rol(), public.revelado(), public.es_pareja(uuid), public.puedo_ver(uuid),
  public.estado_revelacion(), public.marcar_listo(boolean) to authenticated;

-- 6. Reglas de acceso
create policy "perfiles: ver" on public.perfiles for select to authenticated using (public.puedo_ver(id));

create policy "recuerdos: ver"    on public.recuerdos for select to authenticated using (public.puedo_ver(autor));
create policy "recuerdos: crear"  on public.recuerdos for insert to authenticated with check (autor = auth.uid() and public.mi_rol() is not null);
create policy "recuerdos: editar" on public.recuerdos for update to authenticated using (autor = auth.uid()) with check (autor = auth.uid());
create policy "recuerdos: borrar" on public.recuerdos for delete to authenticated using (autor = auth.uid());

create policy "archivos: ver"    on public.archivos for select to authenticated using (public.puedo_ver(autor));
create policy "archivos: crear"  on public.archivos for insert to authenticated with check (autor = auth.uid());
create policy "archivos: borrar" on public.archivos for delete to authenticated using (autor = auth.uid());

-- 7. Almacenamiento privado de fotos y escaneos: cada quien en su carpeta (<su id>/...)
insert into storage.buckets (id, name, public) values ('aportes', 'aportes', false) on conflict do nothing;

create policy "aportes: subir lo mío" on storage.objects for insert to authenticated
  with check (bucket_id = 'aportes' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "aportes: ver" on storage.objects for select to authenticated
  using (bucket_id = 'aportes' and public.puedo_ver(((storage.foldername(name))[1])::uuid));
create policy "aportes: borrar lo mío" on storage.objects for delete to authenticated
  using (bucket_id = 'aportes' and (storage.foldername(name))[1] = auth.uid()::text);
