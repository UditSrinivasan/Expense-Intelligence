import uuid

from sqlalchemy import select

from expense_intelligence.config import Settings, get_settings
from expense_intelligence.main import app
from expense_intelligence.models import ChatMessage, ChatThread, ProductFeedback, User


USER = "00000000-0000-4000-8000-000000000001"
OTHER = "00000000-0000-4000-8000-000000000002"


def auth(user=USER):
    return {"X-Dev-User-Id": user}


def test_tour_state_and_checklist_are_user_scoped(client):
    first = client.get("/v1/experience", headers=auth())
    assert first.status_code == 200
    assert first.json()["tour_state"] == "never_started"
    assert not any(item["completed"] for item in first.json()["checklist"])

    updated = client.put("/v1/experience", headers=auth(), json={"tour_state": "in_progress", "tour_step": 4, "dashboard_reviewed": True})
    assert updated.status_code == 200
    assert updated.json()["tour_step"] == 4
    assert next(item for item in updated.json()["checklist"] if item["key"] == "dashboard")["completed"]

    other = client.get("/v1/experience", headers=auth(OTHER)).json()
    assert other["tour_state"] == "never_started"
    assert not next(item for item in other["checklist"] if item["key"] == "dashboard")["completed"]


def test_tutorial_reconciles_without_persisting_financial_records(client):
    before = client.get("/v1/groups", headers=auth()).json()
    result = client.get("/v1/tutorials/five-friends-split", headers=auth())
    assert result.status_code == 200
    body = result.json()
    assert body["reconciled"] is True
    assert body["total"] == 4798.0
    assert len(body["participants"]) == 5
    assert client.get("/v1/groups", headers=auth()).json() == before


def test_assistant_feedback_requires_owned_assistant_message(client, db):
    client.get("/v1/experience", headers=auth())
    user_id = db.scalar(select(User.id).where(User.auth_subject == f"dev:{USER}"))
    thread = ChatThread(owner_user_id=user_id, title="Synthetic")
    db.add(thread); db.flush()
    message = ChatMessage(owner_user_id=user_id, thread_id=thread.id, role="assistant", content="Synthetic answer")
    db.add(message); db.commit()
    accepted = client.post("/v1/feedback", headers=auth(), json={"kind": "assistant", "sentiment": "helpful", "target_id": str(message.id)})
    assert accepted.status_code == 201
    denied = client.post("/v1/feedback", headers=auth(OTHER), json={"kind": "assistant", "sentiment": "helpful", "target_id": str(message.id)})
    assert denied.status_code == 404


def test_private_beta_feedback_is_minimal_and_admin_review_is_explicit(client, db):
    payload = {"kind": "calculation", "sentiment": "report", "description": "Synthetic rounding concern", "steps": "Open synthetic split", "page_path": "/groups/tutorial", "viewport": "390x844", "contact_allowed": False}
    accepted = client.post("/v1/feedback", headers=auth(), json=payload)
    assert accepted.status_code == 201, accepted.text
    row = db.get(ProductFeedback, uuid.UUID(accepted.json()["id"]))
    assert row.description == "Synthetic rounding concern"
    assert row.owner_user_id == db.scalar(select(User.id).where(User.auth_subject == f"dev:{USER}"))
    assert client.get("/v1/feedback", headers=auth()).status_code == 404
    admin_email = f"dev+{USER}@example.invalid"
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="test", allow_dev_auth=True, feedback_admin_emails=admin_email)
    reviewed = client.get("/v1/feedback", headers=auth())
    assert reviewed.status_code == 200
    assert reviewed.json()[0]["description"] == "Synthetic rounding concern"


def test_feedback_rejects_queries_and_oversized_or_untyped_content(client):
    missing = client.post("/v1/feedback", headers=auth(), json={"kind": "bug", "sentiment": "report"})
    assert missing.status_code == 422
    query = client.post("/v1/feedback", headers=auth(), json={"kind": "bug", "sentiment": "report", "description": "Synthetic", "page_path": "/transactions?account=private"})
    assert query.status_code == 422
