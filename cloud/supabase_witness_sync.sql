-- WITNESS Sync V1 — Supabase hosted backend
-- Run this entire file once in Supabase Dashboard -> SQL Editor.
-- It stores only small JSON sync records. Daily/SOS video files remain local.
-- Desktop clients use only a publishable key. Never put a secret/service-role key in WITNESS.

create extension if not exists pgcrypto;
create schema if not exists witness_private;

create sequence if not exists witness_private.sync_revision_seq;

create table if not exists witness_private.profiles (
    id uuid primary key default gen_random_uuid(),
    secret_hash text not null unique,
    created_at timestamptz not null default now()
);

create table if not exists witness_private.devices (
    profile_id uuid not null references witness_private.profiles(id) on delete cascade,
    device_id text not null,
    device_name text not null default '',
    linked_at timestamptz not null default now(),
    last_seen timestamptz not null default now(),
    primary key(profile_id, device_id)
);

create table if not exists witness_private.items (
    profile_id uuid not null references witness_private.profiles(id) on delete cascade,
    entity_type text not null,
    entity_id text not null,
    payload jsonb not null default '{}'::jsonb,
    modified_ts double precision not null default 0,
    revision bigint not null default nextval('witness_private.sync_revision_seq'),
    source_device text not null default '',
    changed_at timestamptz not null default now(),
    primary key(profile_id, entity_type, entity_id)
);
create index if not exists witness_items_profile_revision
    on witness_private.items(profile_id, revision);

-- Private helper. The link key itself is never stored, only SHA-256.
create or replace function witness_private.profile_for_secret(p_secret text)
returns uuid
language sql
security definer
set search_path = ''
as $$
    select p.id
    from witness_private.profiles p
    where p.secret_hash = encode(extensions.digest(p_secret, 'sha256'), 'hex')
    limit 1
$$;

revoke all on function witness_private.profile_for_secret(text) from public;

create or replace function public.witness_create_profile(
    p_secret text,
    p_device_id text,
    p_device_name text default ''
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_profile uuid;
begin
    if p_secret is null or length(p_secret) < 24 then
        raise exception 'Invalid WITNESS profile secret';
    end if;
    insert into witness_private.profiles(secret_hash)
    values (encode(extensions.digest(p_secret, 'sha256'), 'hex'))
    returning id into v_profile;

    insert into witness_private.devices(profile_id,device_id,device_name)
    values (v_profile, left(coalesce(p_device_id,''),120), left(coalesce(p_device_name,''),120))
    on conflict(profile_id,device_id) do update
       set device_name=excluded.device_name,last_seen=now();
    return v_profile;
end
$$;

create or replace function public.witness_link_profile(
    p_secret text,
    p_device_id text,
    p_device_name text default ''
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_profile uuid;
begin
    v_profile := witness_private.profile_for_secret(p_secret);
    if v_profile is null then
        raise exception 'Unknown WITNESS Link Code';
    end if;
    insert into witness_private.devices(profile_id,device_id,device_name)
    values (v_profile, left(coalesce(p_device_id,''),120), left(coalesce(p_device_name,''),120))
    on conflict(profile_id,device_id) do update
       set device_name=excluded.device_name,last_seen=now();
    return v_profile;
end
$$;

create or replace function public.witness_sync_push(
    p_profile_id uuid,
    p_secret text,
    p_device_id text,
    p_device_name text,
    p_items jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_profile uuid;
    v_item jsonb;
    v_count integer := 0;
    v_revision bigint := 0;
begin
    v_profile := witness_private.profile_for_secret(p_secret);
    if v_profile is null or v_profile <> p_profile_id then
        raise exception 'WITNESS Sync authorization failed';
    end if;

    insert into witness_private.devices(profile_id,device_id,device_name)
    values (v_profile, left(coalesce(p_device_id,''),120), left(coalesce(p_device_name,''),120))
    on conflict(profile_id,device_id) do update
       set device_name=excluded.device_name,last_seen=now();

    if jsonb_typeof(coalesce(p_items, '[]'::jsonb)) <> 'array' then
        raise exception 'p_items must be a JSON array';
    end if;

    for v_item in select value from jsonb_array_elements(coalesce(p_items, '[]'::jsonb))
    loop
        if coalesce(v_item->>'entity_type','') not in ('activity','xp_event','note','state') then
            continue;
        end if;
        if coalesce(v_item->>'entity_id','') = '' then
            continue;
        end if;

        insert into witness_private.items(
            profile_id,entity_type,entity_id,payload,modified_ts,revision,source_device,changed_at)
        values (
            v_profile,
            left(v_item->>'entity_type',40),
            left(v_item->>'entity_id',160),
            coalesce(v_item->'payload','{}'::jsonb),
            coalesce((v_item->>'modified_ts')::double precision,0),
            nextval('witness_private.sync_revision_seq'),
            left(coalesce(p_device_id,''),120),
            now())
        on conflict(profile_id,entity_type,entity_id) do update set
            payload=excluded.payload,
            modified_ts=excluded.modified_ts,
            revision=nextval('witness_private.sync_revision_seq'),
            source_device=excluded.source_device,
            changed_at=now()
        where excluded.modified_ts >= witness_private.items.modified_ts;
        v_count := v_count + 1;
    end loop;

    select coalesce(max(revision),0) into v_revision
    from witness_private.items where profile_id=v_profile;
    return jsonb_build_object('accepted',v_count,'latest_revision',v_revision);
end
$$;

create or replace function public.witness_sync_pull(
    p_profile_id uuid,
    p_secret text,
    p_device_id text,
    p_device_name text,
    p_after_revision bigint default 0,
    p_limit integer default 500
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_profile uuid;
    v_items jsonb;
    v_last bigint;
    v_count integer;
    v_limit integer;
begin
    v_profile := witness_private.profile_for_secret(p_secret);
    if v_profile is null or v_profile <> p_profile_id then
        raise exception 'WITNESS Sync authorization failed';
    end if;
    v_limit := greatest(1, least(coalesce(p_limit,500),1000));

    insert into witness_private.devices(profile_id,device_id,device_name)
    values (v_profile, left(coalesce(p_device_id,''),120), left(coalesce(p_device_name,''),120))
    on conflict(profile_id,device_id) do update
       set device_name=excluded.device_name,last_seen=now();

    with page as (
        select i.revision,i.entity_type,i.entity_id,i.payload,i.modified_ts,i.source_device
        from witness_private.items i
        where i.profile_id=v_profile and i.revision > coalesce(p_after_revision,0)
        order by i.revision
        limit v_limit
    )
    select
        coalesce(jsonb_agg(jsonb_build_object(
            'revision',revision,'entity_type',entity_type,'entity_id',entity_id,
            'payload',payload,'modified_ts',modified_ts,'source_device',source_device)
            order by revision), '[]'::jsonb),
        coalesce(max(revision),coalesce(p_after_revision,0)),
        count(*)
    into v_items,v_last,v_count
    from page;

    return jsonb_build_object(
        'items',v_items,
        'latest_revision',v_last,
        'has_more',(v_count >= v_limit)
    );
end
$$;

-- No desktop client gets direct access to private tables. Only the four narrow
-- profile-secret-checked RPC functions are executable with the public key.
revoke all on schema witness_private from public, anon, authenticated;
revoke all on all tables in schema witness_private from public, anon, authenticated;
revoke all on all sequences in schema witness_private from public, anon, authenticated;

revoke all on function public.witness_create_profile(text,text,text) from public;
revoke all on function public.witness_link_profile(text,text,text) from public;
revoke all on function public.witness_sync_push(uuid,text,text,text,jsonb) from public;
revoke all on function public.witness_sync_pull(uuid,text,text,text,bigint,integer) from public;

grant execute on function public.witness_create_profile(text,text,text) to anon;
grant execute on function public.witness_link_profile(text,text,text) to anon;
grant execute on function public.witness_sync_push(uuid,text,text,text,jsonb) to anon;
grant execute on function public.witness_sync_pull(uuid,text,text,text,bigint,integer) to anon;
