-- MarxBase suggestion queue (Supabase / Postgres). Paste into the project's SQL editor and run once.
-- This is NOT the research database; it only holds suggestions sent from the website.
-- Anyone on the website can INSERT a suggestion (anonymous, no login). Nobody can read, change or delete rows from the
-- browser: only the maintainer, using the service key from the command line (`kmarx.curate suggestions pull`).

create table if not exists public.suggestion (
  id             bigint generated always as identity primary key,
  created_at     timestamptz not null default now(),
  kind           text not null check (kind in ('error_report', 'field_edit', 'missing_result', 'gene_mapping')),
  page_type      text not null check (page_type in ('result', 'gene', 'paper', 'strain', 'product')),
  target_id      text not null check (char_length(target_id) between 1 and 200),
  release_version text not null check (char_length(release_version) between 1 and 40),
  field_name     text check (char_length(field_name) <= 80),
  proposed_value text check (char_length(proposed_value) <= 1000),
  comment        text not null check (char_length(comment) between 3 and 2000),
  evidence       text check (char_length(evidence) <= 2000),
  contact        text check (char_length(contact) <= 200),
  status         text not null default 'open' check (status in ('open', 'accepted', 'rejected', 'deferred'))
);

alter table public.suggestion enable row level security;

-- the only thing the public key may do: insert a row (and only these columns, so status cannot be set)
drop policy if exists "anyone can submit a suggestion" on public.suggestion;
create policy "anyone can submit a suggestion" on public.suggestion
  for insert to anon, authenticated with check (true);

revoke all on public.suggestion from anon, authenticated;
grant insert (kind, page_type, target_id, release_version, field_name, proposed_value, comment, evidence, contact)
  on public.suggestion to anon, authenticated;
-- no select, update or delete policy exists for anon/authenticated, so those are refused.
