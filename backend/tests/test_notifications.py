from tests.conftest import auth_headers, register_user

from app import models


def _get_user_id(db_session, email: str) -> str:
    return db_session.query(models.User).filter(models.User.email == email).one().id


def test_user_cannot_mark_another_users_notification_read(client, db_session):
    register_user(client, "notif-owner@example.com", "Password123!", "doctor")
    register_user(client, "notif-other@example.com", "Password123!", "doctor")
    owner_id = _get_user_id(db_session, "notif-owner@example.com")

    note = models.NotificationItem(user_id=owner_id, title="Private", body="For owner only")
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)

    other_headers = auth_headers(client, "notif-other@example.com", "Password123!")
    resp = client.post(f"/notifications/{note.id}/read", headers=other_headers)
    assert resp.status_code == 403

    db_session.expire_all()
    refreshed = db_session.get(models.NotificationItem, note.id)
    assert refreshed.unread is True


def test_owner_can_mark_own_notification_read(client, db_session):
    register_user(client, "notif-self@example.com", "Password123!", "doctor")
    owner_id = _get_user_id(db_session, "notif-self@example.com")

    note = models.NotificationItem(user_id=owner_id, title="Mine", body="For me")
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)

    owner_headers = auth_headers(client, "notif-self@example.com", "Password123!")
    resp = client.post(f"/notifications/{note.id}/read", headers=owner_headers)
    assert resp.status_code == 200

    db_session.expire_all()
    refreshed = db_session.get(models.NotificationItem, note.id)
    assert refreshed.unread is False


def test_user_can_mark_read_a_broadcast_notification_for_their_role(client, db_session):
    register_user(client, "notif-role@example.com", "Password123!", "doctor")

    note = models.NotificationItem(user_id=None, audience_role="doctor", title="Broadcast", body="All doctors")
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)

    headers = auth_headers(client, "notif-role@example.com", "Password123!")
    resp = client.post(f"/notifications/{note.id}/read", headers=headers)
    assert resp.status_code == 200
