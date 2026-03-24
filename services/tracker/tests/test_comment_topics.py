"""Tests for comment_topics and comment_questions endpoints."""
from tests.conftest import seed_matter


def test_create_comment_topic(client, auth_headers, db):
    """POST /tracker/matters/{id}/comment-topics creates a topic."""
    matter = seed_matter(db)
    payload = {
        "matter_id": matter["id"],
        "topic_label": "Gaming — Scope and Public Interest",
        "topic_area": "public_interest",
        "position_status": "open",
        "priority": "high",
    }
    resp = client.post(f"/tracker/matters/{matter['id']}/comment-topics",
                       json=payload, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data


def test_list_comment_topics(client, auth_headers, db):
    """GET /tracker/matters/{id}/comment-topics lists topics with nested questions."""
    matter = seed_matter(db)
    # Create topic
    payload = {"matter_id": matter["id"], "topic_label": "Test Topic",
               "topic_area": "core_principles"}
    resp = client.post(f"/tracker/matters/{matter['id']}/comment-topics",
                       json=payload, headers=auth_headers)
    topic_id = resp.json()["id"]

    # Add questions
    for i in range(3):
        client.post(f"/tracker/comment-topics/{topic_id}/questions",
                    json={"question_number": str(i+1),
                          "question_text": f"Question {i+1}?"},
                    headers=auth_headers)

    # List
    resp = client.get(f"/tracker/matters/{matter['id']}/comment-topics",
                      headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"][0]["questions"]) == 3


def test_update_comment_topic(client, auth_headers, db):
    """PUT /tracker/comment-topics/{id} updates a topic."""
    matter = seed_matter(db)
    resp = client.post(f"/tracker/matters/{matter['id']}/comment-topics",
                       json={"matter_id": matter["id"],
                             "topic_label": "Original Label"},
                       headers=auth_headers)
    topic_id = resp.json()["id"]

    resp = client.put(f"/tracker/comment-topics/{topic_id}",
                      json={"topic_label": "Updated Label",
                            "position_status": "research"},
                      headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_delete_topic_cascades_questions(client, auth_headers, db):
    """DELETE /tracker/comment-topics/{id} cascades to child questions."""
    matter = seed_matter(db)
    resp = client.post(f"/tracker/matters/{matter['id']}/comment-topics",
                       json={"matter_id": matter["id"],
                             "topic_label": "To Delete"},
                       headers=auth_headers)
    topic_id = resp.json()["id"]

    # Add 2 questions
    for i in range(2):
        client.post(f"/tracker/comment-topics/{topic_id}/questions",
                    json={"question_number": f"Q{i+1}",
                          "question_text": f"Question {i+1}?"},
                    headers=auth_headers)

    # Delete topic
    resp = client.delete(f"/tracker/comment-topics/{topic_id}",
                         headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["questions_deleted"] == 2

    # Verify topic is gone
    resp = client.get(f"/tracker/comment-topics/{topic_id}",
                      headers=auth_headers)
    assert resp.status_code == 404

    # Verify questions are gone
    count = db.execute("SELECT COUNT(*) as c FROM comment_questions WHERE comment_topic_id = ?",
                       (topic_id,)).fetchone()["c"]
    assert count == 0


def test_create_and_update_question(client, auth_headers, db):
    """Question CRUD works."""
    matter = seed_matter(db)
    resp = client.post(f"/tracker/matters/{matter['id']}/comment-topics",
                       json={"matter_id": matter["id"],
                             "topic_label": "Question Test"},
                       headers=auth_headers)
    topic_id = resp.json()["id"]

    # Create question
    resp = client.post(f"/tracker/comment-topics/{topic_id}/questions",
                       json={"question_number": "19a",
                              "question_text": "What sources should inform the Commission?"},
                       headers=auth_headers)
    assert resp.status_code == 200
    qid = resp.json()["id"]

    # Update question text
    resp = client.put(f"/tracker/comment-questions/{qid}",
                      json={"question_text": "Updated question text"},
                      headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["updated"] is True


def test_move_question_between_topics(client, auth_headers, db):
    """PATCH /tracker/comment-questions/{id}/move moves to different topic."""
    matter = seed_matter(db)

    # Create two topics
    resp1 = client.post(f"/tracker/matters/{matter['id']}/comment-topics",
                        json={"matter_id": matter["id"],
                              "topic_label": "Source Topic"},
                        headers=auth_headers)
    source_id = resp1.json()["id"]

    resp2 = client.post(f"/tracker/matters/{matter['id']}/comment-topics",
                        json={"matter_id": matter["id"],
                              "topic_label": "Target Topic"},
                        headers=auth_headers)
    target_id = resp2.json()["id"]

    # Create question in source topic
    resp = client.post(f"/tracker/comment-topics/{source_id}/questions",
                       json={"question_number": "1",
                             "question_text": "Movable question"},
                       headers=auth_headers)
    qid = resp.json()["id"]

    # Move it
    resp = client.patch(f"/tracker/comment-questions/{qid}/move",
                        json={"target_topic_id": target_id},
                        headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["to_topic_id"] == target_id

    # Verify it's now in the target topic
    row = db.execute("SELECT comment_topic_id FROM comment_questions WHERE id = ?",
                     (qid,)).fetchone()
    assert row["comment_topic_id"] == target_id


def test_enum_validation_on_topic(client, auth_headers, db):
    """Invalid enum values are rejected."""
    matter = seed_matter(db)
    payload = {
        "matter_id": matter["id"],
        "topic_label": "Bad Enum Test",
        "topic_area": "nonexistent_area",
    }
    resp = client.post(f"/tracker/matters/{matter['id']}/comment-topics",
                       json=payload, headers=auth_headers)
    assert resp.status_code == 422


def test_topic_filter_by_status(client, auth_headers, db):
    """Filter topics by position_status."""
    matter = seed_matter(db)
    for status in ["open", "research", "final"]:
        client.post(f"/tracker/matters/{matter['id']}/comment-topics",
                    json={"matter_id": matter["id"],
                          "topic_label": f"Topic {status}",
                          "position_status": status},
                    headers=auth_headers)

    resp = client.get(f"/tracker/matters/{matter['id']}/comment-topics",
                      params={"position_status": "open"},
                      headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["position_status"] == "open"
