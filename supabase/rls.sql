-- Defense-in-depth policies for the dedicated, non-owner FastAPI database role.
-- Do not apply while FastAPI connects as postgres/table owner: that role bypasses RLS.

create schema if not exists app_private;
revoke all on schema app_private from public;

create or replace function app_private.user_id() returns uuid
language sql stable as $$ select nullif(current_setting('app.current_user_id', true), '')::uuid $$;

create or replace function app_private.is_group_member(target uuid) returns boolean
language sql stable security definer set search_path = public
as $$ select exists(select 1 from group_members where group_id = target and linked_user_id = app_private.user_id() and active) $$;

revoke all on function app_private.user_id() from public;
revoke all on function app_private.is_group_member(uuid) from public;

-- Direct owner-scoped tables.
do $$
declare table_name text;
begin
  foreach table_name in array array['budgets','budget_revisions','category_aliases','chat_checkpoints','chat_messages','chat_threads','classification_rules','financial_accounts','import_batches','import_mapping_profiles','import_rows','insight_records','merchant_aliases','merchants','receipt_documents','recurring_decisions','transactions','transaction_allocations','user_memories'] loop
    execute format('alter table %I enable row level security', table_name);
    execute format('create policy owner_isolation on %I for all using (owner_user_id = app_private.user_id()) with check (owner_user_id = app_private.user_id())', table_name);
  end loop;
end $$;

alter table analytics_preferences enable row level security;
create policy owner_isolation on analytics_preferences for all using (user_id = app_private.user_id()) with check (user_id = app_private.user_id());
alter table user_preferences enable row level security;
create policy owner_isolation on user_preferences for all using (user_id = app_private.user_id()) with check (user_id = app_private.user_id());
alter table audit_events enable row level security;
create policy owner_isolation on audit_events for all using (actor_user_id = app_private.user_id()) with check (actor_user_id = app_private.user_id());
alter table users enable row level security;
create policy identity_isolation on users for all
using (id = app_private.user_id() or auth_subject = current_setting('app.auth_subject', true))
with check (auth_subject = current_setting('app.auth_subject', true));

-- System categories are readable; user categories remain private.
alter table categories enable row level security;
create policy category_read on categories for select using (owner_user_id is null or owner_user_id = app_private.user_id());
create policy category_write on categories for all using (owner_user_id = app_private.user_id()) with check (owner_user_id = app_private.user_id());

-- Group rows are visible only through active membership. A new group may be inserted,
-- but becomes readable only after its owner membership is inserted in the same transaction.
alter table expense_groups enable row level security;
create policy group_read on expense_groups for select using (app_private.is_group_member(id));
create policy group_insert on expense_groups for insert with check (app_private.user_id() is not null);
create policy group_write on expense_groups for update using (app_private.is_group_member(id));
alter table group_members enable row level security;
create policy member_read on group_members for select using (app_private.is_group_member(group_id));
create policy member_insert on group_members for insert with check (
  app_private.is_group_member(group_id) or
  (linked_user_id = app_private.user_id() and not exists(select 1 from group_members existing where existing.group_id = group_members.group_id))
);
create policy member_write on group_members for update using (app_private.is_group_member(group_id));

do $$
declare table_name text;
begin
  foreach table_name in array array['settlements','shared_expenses','split_templates'] loop
    execute format('alter table %I enable row level security', table_name);
    execute format('create policy group_isolation on %I for all using (app_private.is_group_member(group_id)) with check (app_private.is_group_member(group_id))', table_name);
  end loop;
end $$;

alter table expense_components enable row level security;
create policy group_isolation on expense_components for all using (exists(select 1 from shared_expenses e where e.id=expense_id and app_private.is_group_member(e.group_id))) with check (exists(select 1 from shared_expenses e where e.id=expense_id and app_private.is_group_member(e.group_id)));
alter table expense_payers enable row level security;
create policy group_isolation on expense_payers for all using (exists(select 1 from shared_expenses e where e.id=expense_id and app_private.is_group_member(e.group_id))) with check (exists(select 1 from shared_expenses e where e.id=expense_id and app_private.is_group_member(e.group_id)));
alter table expense_allocations enable row level security;
create policy group_isolation on expense_allocations for all using (exists(select 1 from shared_expenses e where e.id=expense_id and app_private.is_group_member(e.group_id))) with check (exists(select 1 from shared_expenses e where e.id=expense_id and app_private.is_group_member(e.group_id)));

-- Reference data is read-only through the application role.
alter table fx_rates enable row level security;
create policy authenticated_read on fx_rates for select using (app_private.user_id() is not null);
alter table feature_flags enable row level security;
create policy authenticated_read on feature_flags for select using (app_private.user_id() is not null);
