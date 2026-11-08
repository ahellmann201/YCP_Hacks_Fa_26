import base64
import asyncio
import hashlib
import io
import json
import uuid

import pytest
import httpx
from fastapi.testclient import TestClient
from PIL import Image

import main
from background_scanner import QueueStore
from grok_assistant import AssistantService, ProviderError, XAIProvider, make_body, output_text


class MockProvider:
    def __init__(self, text='{"value":"ABC-01","alternatives":[],"explanation":"Visible on crop."}'):
        self.text = text
        self.calls = []

    async def complete(self, body):
        self.calls.append(body)
        return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": self.text}]}],
                "usage": {"input_tokens": 30, "output_tokens": 12}}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("SCANNER_ACCESS_PASSWORD", "test-password")
    monkeypatch.setenv("ASSISTANT_ENABLED", "true")
    monkeypatch.setenv("ASSISTANT_IMAGE_ENABLED", "true")
    monkeypatch.setenv("XAI_API_KEY", "mock-only")
    store = QueueStore(tmp_path / "test.sqlite3")
    provider = MockProvider()
    service = AssistantService(store, provider)
    session = store.create("test")["id"]
    other = store.create("other")["id"]
    record = uuid.uuid4().hex
    folder = tmp_path / "uploads" / record
    run = uuid.uuid4().hex
    analysis = folder / "analysis" / run
    analysis.mkdir(parents=True)
    (folder / "sample.json").write_text(json.dumps({"images": []}))
    Image.new("RGB", (100, 30), "white").save(analysis / "field_machine.jpg")
    store.register(session, record)
    review = {"fields": {"machine": ""}, "label_type": "large", "confirmed": False,
              "evidence": {"run_id": run}, "field_checks": {"machine": ["Missing reading"]}, "ocr_candidates": {"machine": []}}
    with store.connection(write=True) as db:
        db.execute("UPDATE session_samples SET review_json=? WHERE record_id=?", (json.dumps(review), record))
        db.execute("UPDATE scan_jobs SET state='done' WHERE record_id=?", (record,))
    monkeypatch.setattr(main, "STORE", store)
    monkeypatch.setattr(main, "ASSISTANT", service)
    monkeypatch.setattr(main, "UPLOADS", tmp_path / "uploads")
    auth = {"Authorization": "Basic " + base64.b64encode(b"clerk:test-password").decode()}
    return TestClient(main.app), service, provider, store, session, other, record, auth


def request(revision=0, action="read", field="machine", consent=True, request_id=None):
    return {"action": action, "field": field, "revision": revision,
            "request_id": request_id or uuid.uuid4().hex, "image_consent": consent}


def test_auth_and_cross_session(setup):
    client, _, provider, _, session, other, record, auth = setup
    assert client.get("/sessions").status_code == 401
    assert client.get("/sessions", headers={"Authorization":"Basic !!!"}).status_code == 401
    assert client.get("/sessions", headers=auth).status_code == 200
    assert client.get(f"/samples/{record}/fields/machine").status_code == 401
    assert client.post(f"/sessions/{other}/samples/{record}/assistant", json=request(), headers=auth).status_code == 404
    assert not provider.calls
    assert client.post(f"/sessions/{session}/samples/{record}/assistant", json=request(), headers={**auth,"Origin":"https://evil.example"}).status_code == 403


def test_opt_in_and_duplicate(setup, monkeypatch):
    client, _, provider, _, session, _, record, auth = setup
    url=f"/sessions/{session}/samples/{record}/assistant"
    assert client.post(url, json=request(consent=False), headers=auth).status_code == 400
    monkeypatch.setenv("ASSISTANT_ENABLED", "false")
    assert client.post(url, json=request(), headers=auth).status_code == 503
    monkeypatch.setenv("ASSISTANT_ENABLED", "true")
    payload=request()
    first=client.post(url, json=payload, headers=auth)
    assert first.status_code == 200, first.text
    assert first.json()["proposal"]["value"] == "ABC-01"
    assert len(provider.calls) == 1
    assert provider.calls[0]["store"] is False
    assert provider.calls[0]["tools"] == []
    assert provider.calls[0]["input"][1]["content"][1]["type"] == "input_image"
    assert provider.calls[0]["input"][1]["content"][1]["image_url"].startswith("data:image/jpeg;base64,")
    assert client.post(url, json=payload, headers=auth).json() == first.json()
    assert len(provider.calls) == 1


def test_stale_and_finish(setup):
    client, _, provider, store, session, _, record, auth = setup
    url=f"/sessions/{session}/samples/{record}/assistant"
    store.edit(session, record, {"machine": "Local"}, "large", False)
    assert client.post(url, json=request(), headers=auth).status_code == 409
    assert not provider.calls
    assert client.post(url, json=request(revision=1), headers=auth).status_code == 200
    store.finish(session)
    assert client.post(url, json=request(revision=1), headers=auth).status_code == 404


def test_apply_suggestion_needs_confirmation(setup):
    client, _, _, store, session, _, record, auth = setup
    payload=request()
    result=client.post(f"/sessions/{session}/samples/{record}/assistant", json=payload, headers=auth)
    assert result.status_code == 200
    review=client.post(f"/samples/{record}/review", headers=auth, json={
        "session_id":session, "label_type":"large", "confirmed":False,
        "fields":{"machine":"ABC-01"}, "expected_revision":0,
        "suggestion_request_id":payload["request_id"], "suggestion_field":"machine"})
    assert review.status_code == 200, review.text
    saved=review.json()["review"]
    assert saved["confirmed"] is False
    assert saved["fields"]["machine"] == "ABC-01"
    assert saved["suggestion_sources"]["machine"]["request_id"] == payload["request_id"]
    assert client.post(f"/samples/{record}/review", headers=auth, json={
        "session_id":session, "label_type":"large", "confirmed":False,
        "fields":{"machine":"ABC-01"}, "expected_revision":0,
        "suggestion_request_id":payload["request_id"], "suggestion_field":"machine"}).status_code == 409


def test_limits_and_bad_response(setup):
    client, _, provider, _, session, _, record, auth = setup
    url=f"/sessions/{session}/samples/{record}/assistant"
    assert client.post(url, json=request(field="other"), headers=auth).status_code == 422
    assert client.post(url, json={**request(), "message":"x"*501}, headers=auth).status_code == 422
    provider.text = "not json"
    assert client.post(url, json=request(), headers=auth).status_code == 503
    with pytest.raises(ProviderError): output_text({"status":"incomplete", "output":[]})
    body = make_body("explain", "machine", "why", {"label_type":"large","fields":{"machine":"X"},"field_checks":{"machine":["Missing reading"]}})
    assert "input_image" not in json.dumps(body)
    image = Image.new("RGB", (100, 30), "white")
    data=io.BytesIO(); image.save(data,"JPEG")
    assert data.getvalue()


def test_finish_while_request_pending_discards_reply(setup):
    client, service, _, store, session, _, record, auth = setup
    store.edit(session, record, {"machine":"Local"}, "large", True)
    class FinishingProvider(MockProvider):
        async def complete(self, body):
            digest=hashlib.sha256(main.csv_bytes(store.reviews(session))).hexdigest()
            store.finish_for_export(session, digest, False, main.csv_bytes)
            return await super().complete(body)
    service.provider=FinishingProvider()
    response=client.post(f"/sessions/{session}/samples/{record}/assistant",
        json=request(revision=1,action="explain"),headers=auth)
    assert response.status_code == 409
    with store.connection() as db:
        row=db.execute("SELECT state,result_json FROM assistant_requests").fetchone()
    assert row["state"] == "finished" and row["result_json"] is None


def test_csv_formula_policy():
    assert main.csv_safe("=1+1") == "'=1+1"
    assert main.csv_safe("  @SUM(A1)") == "'  @SUM(A1)"
    assert main.csv_safe("normal") == "normal"


def test_daily_budget(setup, monkeypatch):
    client, _, provider, _, session, _, record, auth = setup
    monkeypatch.setenv("ASSISTANT_DAILY_REQUESTS", "1")
    url=f"/sessions/{session}/samples/{record}/assistant"
    assert client.post(url, json=request(action="explain"), headers=auth).status_code == 200
    assert client.post(url, json=request(action="explain"), headers=auth).status_code == 429
    assert len(provider.calls) == 1


@pytest.mark.parametrize("status,code", [(401,"credentials"),(402,"credits"),(429,"rate_limit"),(500,"server")])
def test_provider_http_errors(monkeypatch, status, code):
    original=httpx.AsyncClient
    transport=httpx.MockTransport(lambda _: httpx.Response(status))
    monkeypatch.setattr(httpx,"AsyncClient",lambda **kwargs: original(transport=transport,**kwargs))
    monkeypatch.setenv("XAI_API_KEY","mock-only")
    with pytest.raises(ProviderError) as error:
        asyncio.run(XAIProvider().complete({"model":"grok-4.7","input":"test","store":False}))
    assert error.value.code == code
