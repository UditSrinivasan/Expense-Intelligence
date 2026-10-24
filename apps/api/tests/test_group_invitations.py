from sqlalchemy import select
import uuid

from expense_intelligence.models import GroupInvitation, GroupMember
from test_splitting import headers


OTHER = "00000000-0000-4000-8000-000000000002"


def setup_guest(client):
    group = client.post("/v1/groups", headers=headers(), json={"name":"Hosted demo", "default_currency":"INR", "owner_name":"Owner"}).json()
    guest = client.post(f"/v1/groups/{group['id']}/members", headers=headers(), json={"display_name":"Historic guest"}).json()
    return group, guest


def test_invitation_claim_links_existing_guest_without_changing_member_id(client, db):
    group, guest = setup_guest(client)
    email = f"dev+{OTHER}@example.invalid"
    created = client.post(f"/v1/groups/{group['id']}/invitations", headers=headers(), json={"guest_member_id":guest["id"], "email":email, "expires_in_hours":24})
    assert created.status_code == 201
    claimed = client.post("/v1/group-invitations/claim", headers=headers(OTHER), json={"token":created.json()["token"]})
    assert claimed.status_code == 200
    assert claimed.json()["member_id"] == guest["id"]
    member = db.get(GroupMember, uuid.UUID(guest["id"]))
    assert member.linked_user_id is not None and member.guest_name is None


def test_invitation_rejects_wrong_account_and_revocation(client, db):
    group, guest = setup_guest(client)
    email = f"dev+{OTHER}@example.invalid"
    created = client.post(f"/v1/groups/{group['id']}/invitations", headers=headers(), json={"guest_member_id":guest["id"], "email":email}).json()
    assert client.post("/v1/group-invitations/claim", headers=headers(), json={"token":created["token"]}).status_code == 403
    assert client.delete(f"/v1/groups/{group['id']}/invitations/{created['id']}", headers=headers()).status_code == 204
    assert client.post("/v1/group-invitations/claim", headers=headers(OTHER), json={"token":created["token"]}).status_code == 404
    invitation = db.scalar(select(GroupInvitation).where(GroupInvitation.id == uuid.UUID(created["id"])))
    assert invitation.revoked_at is not None
