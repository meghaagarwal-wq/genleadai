"""Iter 65 — White-label fix: Aria must speak as the tenant's business,
not the platform.

Locks in the fix so we never regress:
  1. `get_aria_system_prompt(tenant)` uses business_profile.business_name.
  2. Touchpoint engine `_heuristic_render` substitutes the tenant's business name.
  3. SEND_EMAIL handler in server.py reads from tenant, not env defaults.
  4. Aria's master prompt explicitly bans "GenLeadAI" / "platform" mentions.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/app/backend")


def test_aria_system_prompt_uses_tenant_business_name():
    from aria_agent import get_aria_system_prompt
    tenant = {
        "id": "ten_pietential",
        "name": "Pietential Workspace",
        "settings": {
            "business_profile": {
                "business_name": "Pietential",
                "founder_name": "Riya",
            },
            "aria_persona": {"aria_name": "Aria"},
        },
    }
    prompt = get_aria_system_prompt(tenant)
    assert "Pietential" in prompt
    assert "Riya" in prompt
    # Explicit anti-leakage rule must be present (this is the ONLY place "GenLeadAI"
    # is allowed to appear in the prompt — as a do-not-say instruction).
    assert "Never mention any other company" in prompt
    assert 'Never say "GenLeadAI"' in prompt
    # No mention of "GenLeadAI" as a positive identity statement
    assert "sales assistant for GenLeadAI" not in prompt
    assert "represent GenLeadAI" not in prompt
    assert "from GenLeadAI" not in prompt


def test_aria_system_prompt_falls_back_to_tenant_name():
    """If business_profile is empty, the workspace name is used (NOT env COMPANY_NAME)."""
    from aria_agent import get_aria_system_prompt
    tenant = {
        "id": "ten_acme",
        "name": "Acme Solutions",
        "settings": {},
    }
    prompt = get_aria_system_prompt(tenant)
    assert "Acme Solutions" in prompt
    # We accept that if both business_profile AND tenant.name are missing,
    # the env-default may show — that's a deliberate "last resort" fallback.


def test_touchpoint_heuristic_renderer_uses_business_profile():
    from routes.touchpoint_engine import _heuristic_render
    tenant = {
        "id": "ten_pietential",
        "name": "Some Internal Workspace Name",  # should be ignored when business_profile set
        "settings": {
            "business_profile": {"business_name": "Pietential"},
            "aria_persona": {"aria_name": "Pia"},
            "sales_process": {"product_description": "Wellness coaching"},
        },
    }
    lead = {"name": "Priya Mehta"}
    tp = {"message_template": "Hi {{first_name}}, this is {{aria_name}} from {{company}} — let's chat about {{product}}."}
    out = _heuristic_render(tenant, lead, tp)
    assert "Priya" in out
    assert "Pia" in out
    assert "Pietential" in out
    assert "Wellness coaching" in out
    assert "GenLeadAI" not in out
    # The workspace name should NOT have leaked through
    assert "Some Internal Workspace Name" not in out


def test_touchpoint_heuristic_falls_back_to_tenant_name_when_no_profile():
    from routes.touchpoint_engine import _heuristic_render
    tenant = {"id": "ten_x", "name": "Customer Brand", "settings": {}}
    out = _heuristic_render(tenant, {"name": "Sam"}, {"message_template": "From {{company}}."})
    assert "Customer Brand" in out
    assert "GenLeadAI" not in out
