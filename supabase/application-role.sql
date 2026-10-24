-- REVIEW-ONLY: run as the hosted database owner only after explicit approval.
-- Set the LOGIN password separately through a secret-safe Supabase SQL session.
do $$
begin
  if not exists(select 1 from pg_roles where rolname = 'expense_app') then
    create role expense_app login nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end $$;

revoke create on schema public from public;
grant connect on database postgres to expense_app;
grant usage on schema public, app_private to expense_app;
grant select, insert, update, delete on all tables in schema public to expense_app;
grant usage, select on all sequences in schema public to expense_app;
grant execute on function app_private.user_id() to expense_app;
grant execute on function app_private.is_group_member(uuid) to expense_app;
grant execute on function app_private.is_group_owner(uuid) to expense_app;

alter default privileges in schema public grant select, insert, update, delete on tables to expense_app;
alter default privileges in schema public grant usage, select on sequences to expense_app;
