"""iter124 — Tests for the 32-Touchpoint Journey, KB RAG, and prompt sanitiser wiring.

Run:  pytest tests/test_iter124_close_it_out.py -v
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Journey CRUD (in-memory mongo via the global db) ───────────────────
class TestJourneyCRUD:
    def test_create_list_patch_delete_cycle(self):
        from routes import journey
        from deps import db

        col = db["journey_touchpoints"]
        tenant = {"id": "ten_test_iter124"}
        col.delete_many({"tenant_id": tenant["id"]})

        import asyncio
        from routes.journey import TouchpointIn, TouchpointPatch, list_touchpoints, create_touchpoint, patch_touchpoint, delete_touchpoint

        # CREATE
        created = asyncio.run(create_touchpoint(
            TouchpointIn(number=1, channel="whatsapp", timing="Day 1",
                         message_body="Hi {{first_name}}", goal="open",
                         conditional_logic="if no reply day 3 → email"),
            tenant=tenant,
        ))
        assert created["channel"] == "whatsapp"
        assert created["generated_by"] == "manual"
        assert created["id"].startswith("tp_")

        # LIST
        listed = asyncio.run(list_touchpoints(tenant=tenant))
        assert listed["count"] == 1

        # PATCH
        patched = asyncio.run(patch_touchpoint(
            created["id"],
            TouchpointPatch(goal="get reply", channel="email"),
            tenant=tenant,
        ))
        assert patched["goal"] == "get reply"
        assert patched["channel"] == "email"

        # DELETE
        result = asyncio.run(delete_touchpoint(created["id"], tenant=tenant))
        assert result == {"status": "ok"}
        assert col.count_documents({"tenant_id": tenant["id"]}) == 0

    def test_create_rejects_invalid_channel(self):
        from routes.journey import TouchpointIn, create_touchpoint
        from fastapi import HTTPException
        import asyncio

        with pytest.raises(HTTPException) as exc:
            asyncio.run(create_touchpoint(
                TouchpointIn(number=1, channel="fax", timing="Day 1"),
                tenant={"id": "ten_test_iter124"},
            ))
        assert exc.value.status_code == 400


# ─── KB RAG scoring (deterministic, no Claude) ──────────────────────────
class TestKbRagScoring:
    def test_score_jaccard_overlap(self):
        from services.kb_rag_service import _score, _tokens
        chunk = "ARIA is a sales platform that automates outbound for founders."
        kws = ["sales", "platform", "founders"]
        s = _score(kws, chunk)
        assert s > 0
        # No overlap
        assert _score(["banana", "carrot"], chunk) == 0.0

    def test_tokens_drops_stopwords(self):
        from services.kb_rag_service import _tokens
        toks = _tokens("the and of for sales platform")
        # Stop words and tokens <3 chars are dropped
        assert "the" not in toks
        assert "sales" in toks
        assert "platform" in toks


# ─── Sanitiser wiring (just confirm the flag flips through) ─────────────
class TestSanitizerWiring:
    def test_inbound_reply_passes_sanitize_flag(self):
        # Grep-style assert: the inbound reply qualifier must opt-in.
        with open("/app/backend/routes/inbound_reply.py", "r") as f:
            src = f.read()
        assert "sanitize_user_input=True" in src, "inbound_reply must sanitise lead-sourced text"

    def test_classification_passes_sanitize_flag(self):
        with open("/app/backend/routes/classification.py", "r") as f:
            src = f.read()
        assert "sanitize_user_input=True" in src, "classification must sanitise lead-sourced text"

    def test_workspace_reply_passes_sanitize_flag(self):
        with open("/app/backend/aria_agent_routes/workspace.py", "r") as f:
            src = f.read()
        assert "sanitize_user_input=True" in src, "workspace reply must sanitise"


# ─── IG/FB crawl hooks exist ────────────────────────────────────────────
class TestSocialCrawlHooks:
    def test_instagram_helper_exists(self):
        from services.crawl_service import serper_instagram_search
        assert callable(serper_instagram_search)

    def test_facebook_helper_exists(self):
        from services.crawl_service import serper_facebook_search
        assert callable(serper_facebook_search)
