-- One-shot additive migration. Never reapply 001 or rerun this on existing objects.
begin;
do $$
begin
    if exists (select 1 from pg_catalog.pg_extension e
               join pg_catalog.pg_namespace n on n.oid = e.extnamespace
               where e.extname = 'vector' and n.nspname <> 'extensions') then
        raise exception 'Unexpected vector schema';
    end if;
    if pg_catalog.to_regclass('public.editorial_card_embeddings') is not null
       or pg_catalog.to_regclass('public.editorial_runtime_library') is not null
       or exists (select 1 from pg_catalog.pg_proc p join pg_catalog.pg_namespace n
                  on n.oid = p.pronamespace where n.nspname = 'public'
                  and p.proname = 'editorial_content_fingerprint') then
        raise exception 'Unexpected existing editorial objects';
    end if;
end $$;
create extension if not exists vector with schema extensions;

-- Decimal UTF-8 BYTE lengths, colon, then original UTF-8 bytes, no separator.
-- Fixed order mirrors CONTENT_FIELDS; status and approval are deliberately absent.
create function public.editorial_content_fingerprint(c public.editorial_cards)
returns text language sql immutable strict set search_path = '' as $$
    select pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
        pg_catalog.string_agg(pg_catalog.octet_length(pg_catalog.convert_to(v, 'UTF8'))::text
                              || ':' || v, '' order by ordinal), 'UTF8')), 'hex')
    from pg_catalog.unnest(array[c.owner_id::text, c.card_id, c.provenance_id,
        c.phase, c.gate, c.situation, c.last_assistant_move, c.proposed_move,
        c.positive_voice, c.negative_repetition,
        case when c.sanitized then 'true' else 'false' end])
        with ordinality as content(v, ordinal)
$$;
revoke all on function public.editorial_content_fingerprint(public.editorial_cards)
    from public, anon, authenticated;
grant execute on function public.editorial_content_fingerprint(public.editorial_cards)
    to authenticated;

create table public.editorial_card_embeddings (
    owner_id uuid not null,
    card_id text not null,
    approval_id text not null check (approval_id ~ '^[a-z0-9][a-z0-9_-]{0,79}$'),
    fingerprint text not null check (fingerprint ~ '^[0-9a-f]{64}$'),
    model text not null check (length(model) between 1 and 200),
    revision text not null check (revision ~ '^[0-9a-f]{40}$'),
    spec_version text not null check (length(spec_version) between 1 and 200),
    preprocessing_version text not null check (length(preprocessing_version) between 1 and 200),
    runtime_version text not null check (length(runtime_version) between 1 and 80),
    graph_sha256 text not null check (graph_sha256 ~ '^[0-9a-f]{64}$'),
    dimensions integer not null check (dimensions = 384),
    embedding extensions.vector(384) not null,
    primary key (owner_id, card_id),
    foreign key (owner_id, card_id) references public.editorial_cards(owner_id, card_id)
        on delete cascade,
    check (extensions.vector_norm(embedding) between 0.9999 and 1.0001)
);
alter table public.editorial_card_embeddings enable row level security;
alter table public.editorial_card_embeddings force row level security;
revoke all on public.editorial_card_embeddings from public, anon, authenticated;
grant select on public.editorial_card_embeddings to authenticated;
create policy editorial_embedding_select on public.editorial_card_embeddings
    for select to authenticated using ((select auth.uid()) = owner_id);

create view public.editorial_runtime_library with (security_invoker = true) as
select c.owner_id, c.card_id, c.provenance_id, c.status, c.sanitized, c.phase,
       c.gate, c.situation, c.last_assistant_move, c.proposed_move, c.positive_voice,
       c.negative_repetition, c.approval_id, e.fingerprint, e.model, e.revision,
       e.spec_version, e.preprocessing_version, e.runtime_version, e.graph_sha256,
       e.dimensions, e.embedding::text as embedding
from public.editorial_cards c
join public.editorial_card_embeddings e
    on c.owner_id = e.owner_id and c.card_id = e.card_id
    and c.approval_id = e.approval_id
    and public.editorial_content_fingerprint(c) = e.fingerprint
where c.status = 'approved' and c.sanitized = true;
revoke all on public.editorial_runtime_library from public, anon, authenticated;
grant select on public.editorial_runtime_library to authenticated;
comment on table public.editorial_card_embeddings is
    'Admin-seeded criterion vectors only. Never lead text, query vectors or source uploads.';
commit;
