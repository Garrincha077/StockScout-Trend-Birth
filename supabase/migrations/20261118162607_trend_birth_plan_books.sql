begin;

create schema if not exists stockscout_unified_api;

create table stockscout_unified_api.trend_birth_plan_books (
  user_id uuid primary key references auth.users(id) on delete cascade,
  version integer not null check (version > 0),
  plans jsonb not null,
  constraint trend_birth_plan_book_size check (
    case when jsonb_typeof(plans) = 'array' then
      jsonb_array_length(plans) <= 1000 and octet_length(plans::text) <= 524288
    else false end
  )
);

alter table stockscout_unified_api.trend_birth_plan_books enable row level security;
revoke all on stockscout_unified_api.trend_birth_plan_books from public, anon, authenticated;
grant usage on schema stockscout_unified_api to authenticated;
grant select, insert, update on stockscout_unified_api.trend_birth_plan_books to authenticated;

create policy trend_birth_plan_book_owner
  on stockscout_unified_api.trend_birth_plan_books
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create function stockscout_unified_api.trend_birth_commit_plan_book(
  p_owner uuid,
  p_expected_version integer,
  p_plans jsonb
)
returns integer
language plpgsql
security invoker
set search_path = ''
as $$
declare
  next_version integer;
begin
  if p_owner is null or p_owner is distinct from (select auth.uid()) then
    raise insufficient_privilege using message = 'The current account does not own this plan book';
  end if;
  if p_expected_version is null or p_expected_version < 0 then
    raise invalid_parameter_value using message = 'Invalid plan book version';
  end if;

  if p_expected_version = 0 then
    insert into stockscout_unified_api.trend_birth_plan_books(user_id, version, plans)
    values (p_owner, 1, p_plans)
    on conflict (user_id) do nothing
    returning version into next_version;
  else
    update stockscout_unified_api.trend_birth_plan_books
    set version = version + 1, plans = p_plans
    where user_id = p_owner and version = p_expected_version
    returning version into next_version;
  end if;
  return next_version;
end;
$$;

revoke all on function stockscout_unified_api.trend_birth_commit_plan_book(uuid, integer, jsonb)
  from public, anon, authenticated;
grant execute on function stockscout_unified_api.trend_birth_commit_plan_book(uuid, integer, jsonb)
  to authenticated;

commit;
