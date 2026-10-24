-- REVIEW-ONLY: run as expense_migrator after Alembic and rls.sql, after explicit approval.
grant usage on schema public, app_private to expense_app;
grant select, insert, update, delete on all tables in schema public to expense_app;
grant usage, select on all sequences in schema public to expense_app;
grant execute on function app_private.user_id() to expense_app;
grant execute on function app_private.is_group_member(uuid) to expense_app;
grant execute on function app_private.is_group_owner(uuid) to expense_app;

alter default privileges for role expense_migrator in schema public grant select, insert, update, delete on tables to expense_app;
alter default privileges for role expense_migrator in schema public grant usage, select on sequences to expense_app;
