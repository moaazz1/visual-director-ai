import base64
import io
import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from api import director, storage
from api.main import app
from api.schemas import DOMAINS, TREATMENTS


def sample_file():
    return Path("web/public/sample-campaign.jpg").read_bytes()


def provider_output():
    # Test-only provider fixture. Never served as app content.
    finding = {"observation": "The can sits on the left.", "assumption": "None",
               "recommendation": "Add a narrow edge highlight.", "rationale": "Separates the can from the backdrop."}
    return {
        "verdict": "The product reads against the backdrop.",
        "preserve": ["Can placement"],
        "priorities": [{"issue": "Dim rim", "action": "Add a narrow edge highlight.", "rationale": "Improve silhouette."}],
        "review": {key: finding for key in DOMAINS},
        "treatments": [{"name": name, "direction": f"Execute {name}.", "rationale": "Improve product clarity.",
                        "changes": ["Add controlled rim light."], "preserve": ["Can shape"], "avoid": ["Crushed shadows"],
                        "execution": "Place a strip light behind the can at camera left."} for name in TREATMENTS],
    }


def test_complete_pipeline(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATA", tmp_path)
    monkeypatch.delenv("VISION_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(app) as client:
        config = client.get("/config").json()
        assert config["vision_configured"] is False
        assert client.post("/assets", files={"file": ("bad.jpg", b"broken", "image/jpeg")}).status_code == 415
        assert client.post("/assets", files={"file": ("large.jpg", b"x" * (15 * 1024 * 1024 + 1), "image/jpeg")}).status_code == 413
        original = sample_file()
        uploaded = client.post("/assets", files={"file": ("campaign.jpg", original, "image/jpeg")})
        assert uploaded.status_code == 201
        asset = uploaded.json()
        assert asset["width"] > asset["height"]
        assert client.get(f"/assets/{asset['id']}/image").content == original
        cookie = client.cookies.get("director_session")
        client.cookies.clear()
        assert client.get(f"/assets/{asset['id']}/image").status_code == 404
        client.cookies.set("director_session", cookie)
        body = {"asset_id": asset["id"], "brief": "Make the beverage immediately legible.", "brand": config["sample_brand"]}
        assert client.post("/audits", json=body).status_code == 503
        monkeypatch.setenv("VISION_API_KEY", "test-key")

        def provider(endpoint, *, headers, json, timeout):
            assert endpoint.endswith("/responses")
            assert headers["Authorization"] == "Bearer test-key"
            assert json["store"] is False
            assert json["text"]["format"]["strict"] is True
            assert json["text"]["format"]["schema"]["additionalProperties"] is False
            inputs = json["input"][0]["content"]
            assert "Make the beverage immediately legible." in inputs[0]["text"]
            data = base64.b64decode(inputs[1]["image_url"].split(",", 1)[1])
            with Image.open(io.BytesIO(data)) as frame:
                assert frame.width > frame.height
            return director.httpx.Response(200, request=director.httpx.Request("POST", endpoint),
                json={"status": "completed", "output": [{"type": "message", "content": [
                    {"type": "output_text", "text": response_text}]}]})

        response_text = '{"verdict": "Incomplete"}'
        monkeypatch.setattr(director.httpx, "post", provider)
        assert client.post("/audits", json=body).status_code == 502
        response_text = json.dumps(provider_output())
        result = client.post("/audits", json=body)
        assert result.status_code == 201, result.text
        audit = result.json()
        assert len(audit["result"]["review"]) == 10
        path = f"/audits/{audit['id']}/prompts"
        for name in TREATMENTS:
            prompt = client.post(path, json={"treatment": name})
            assert prompt.status_code == 201
            assert name in prompt.json()["text"]
            assert config["sample_brand"]["locked"] in prompt.json()["text"]
        assert client.post(path, json={"treatment": TREATMENTS[0], "text": "   "}).status_code == 422
        assert client.post(path, json={"treatment": TREATMENTS[0], "text": "Edited direction."}).status_code == 201
    with TestClient(app) as restarted:
        restarted.cookies.set("director_session", cookie)
        restored = restarted.get(f"/assets/{asset['id']}/audit").json()
        assert restored["audit"]["id"] == audit["id"]
        assert restored["request"]["brief"] == body["brief"]
        assert restored["prompt"] == {"text": "Edited direction.", "treatment": TREATMENTS[0]}


def test_gemini_request_and_quota(monkeypatch):
    from uuid import uuid4

    import httpx
    import pytest
    from api.schemas import AuditRequest

    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    provider = director.vision_provider()
    status = 200

    def respond(endpoint, *, headers, json, timeout):
        assert endpoint.endswith(":generateContent")
        assert headers == {"x-goog-api-key": "test-only"}
        assert json["generationConfig"]["responseMimeType"] == "application/json"
        assert json["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "image/jpeg"
        result = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": "internal", "thought": True},
            {"text": serialized},
        ]}}]}
        return httpx.Response(status, request=httpx.Request("POST", endpoint), json=result)

    monkeypatch.setattr(director.httpx, "post", respond)
    request = AuditRequest(asset_id=uuid4())
    serialized = json.dumps(provider_output())
    assert provider.analyze(sample_file(), request).verdict == provider_output()["verdict"]
    status = 429
    with pytest.raises(director.ProviderError, match="quota"):
        provider.analyze(sample_file(), request)
