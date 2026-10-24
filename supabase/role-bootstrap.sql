-- REVIEW-ONLY: run once as the hosted database owner before Alembic, after explicit approval.
-- Set both LOGIN passwords separately in a secret-safe SQL session.
do $$
begin
  if not exists(select 1 from pg_roles where rolname = 'expense_migrator') then
    create role expense_migrator login nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
  if not exists(select 1 from pg_roles where rolname = 'expense_app') then
    create role expense_app login nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end $$;

revoke create on schema public from public;
do $$
begin
  execute format('grant connect, create on database %I to expense_migrator', current_database());
  execute format('grant connect on database %I to expense_app', current_database());
end $$;
grant usage, create on schema public to expense_migrator;
grant usage on schema public to expense_app;

alter default privileges for role expense_migrator in schema public
  grant select, insert, update, delete on tables to expense_app;
alter default privileges for role expense_migrator in schema public
  grant usage, select on sequences to expense_app;
