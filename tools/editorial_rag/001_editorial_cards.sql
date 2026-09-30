-- Offline migration candidate. HUMAN review/application only in the confirmed project.
-- No source corpus, storage buckets, extensions, vectors, seeds or credentials.
-- One-shot transaction: object collisions abort; never reuse or replace existing objects.
begin;

create table public.editorial_cards (
    owner_id uuid not null references auth.users(id) on delete cascade,
    card_id text not null check (card_id ~ '^[a-z0-9][a-z0-9_-]{0,79}$'),
    provenance_id text not null check (provenance_id ~ '^[a-z0-9][a-z0-9_-]{0,79}$'),
    status text not null default 'candidate'
        check (status in ('candidate', 'approved', 'rejected', 'deferred')),
    sanitized boolean not null check (sanitized = true),
    phase text not null check (phase in
        ('contexto', 'destino', 'brecha', 'sentido', 'disposicion', 'ruta', 'conversion')),
    gate text not null check (gate ~ '^[a-z0-9][a-z0-9_-]{0,79}$'),
    situation text not null check (length(btrim(situation)) > 0 and length(situation) <= 2000),
    last_assistant_move text not null
        check (last_assistant_move ~ '^[a-z0-9][a-z0-9_-]{0,79}$'),
    proposed_move text not null check (proposed_move ~ '^[a-z0-9][a-z0-9_-]{0,79}$'),
    positive_voice text not null
        check (length(btrim(positive_voice)) > 0 and length(positive_voice) <= 2000),
    negative_repetition text not null
        check (length(btrim(negative_repetition)) > 0 and length(negative_repetition) <= 2000),
    approval_id text check (approval_id ~ '^[a-z0-9][a-z0-9_-]{0,79}$'),
    primary key (owner_id, card_id),
    check (owner_id <> '00000000-0000-0000-0000-000000000000'::uuid),
    check ((status = 'approved' and approval_id is not null)
        or (status <> 'approved' and approval_id is null))
);

alter table public.editorial_cards enable row level security;
alter table public.editorial_cards force row level security;
revoke all on public.editorial_cards from public, anon, authenticated;
-- Never grant status/approval writes through the authenticated REST role.
grant select, delete on public.editorial_cards to authenticated;
grant insert (owner_id, card_id, provenance_id, sanitized, phase, gate, situation,
    last_assistant_move, proposed_move, positive_voice, negative_repetition)
    on public.editorial_cards to authenticated;
grant update (provenance_id, sanitized, phase, gate, situation,
    last_assistant_move, proposed_move, positive_voice, negative_repetition)
    on public.editorial_cards to authenticated;

create policy editorial_select on public.editorial_cards for select to authenticated
    using ((select auth.uid()) = owner_id);
create policy editorial_insert on public.editorial_cards for insert to authenticated
    with check ((select auth.uid()) = owner_id and status = 'candidate' and approval_id is null);
create policy editorial_update on public.editorial_cards for update to authenticated
    using ((select auth.uid()) = owner_id)
    with check ((select auth.uid()) = owner_id);
create policy editorial_delete on public.editorial_cards for delete to authenticated
    using ((select auth.uid()) = owner_id);

-- Any editorial modification invalidates approval, even for privileged edits.
-- Approval must be a separate human-reviewed administrative transaction.
create function public.editorial_invalidate_approval()
returns trigger language plpgsql set search_path = '' as $$
begin
    if (to_jsonb(new) - 'status' - 'approval_id')
        is distinct from (to_jsonb(old) - 'status' - 'approval_id') then
        new.status := 'candidate';
        new.approval_id := null;
    end if;
    return new;
end $$;
revoke all on function public.editorial_invalidate_approval() from public, anon, authenticated;
create trigger editorial_invalidate_approval
    before update on public.editorial_cards
    for each row execute function public.editorial_invalidate_approval();

comment on table public.editorial_cards is
    'Curated sanitized editorial criteria only. No conversations, quotes, people, paths or source uploads. Approval never changes runtime rules.';
commit;
