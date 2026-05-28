"""Centralised route registration for FastAPI.

iter91 — extracts the long `app.include_router(...)` block from
`server.py` (~50 lines of boilerplate) into a single
`register_all_routes(app)` entry point. Imports are done locally inside
the function so importing this package does NOT eagerly load every route
module — useful for ad-hoc scripts that need a single helper without
spinning up the whole HTTP layer.
"""
from __future__ import annotations

from fastapi import FastAPI


def register_all_routes(app: FastAPI) -> None:
    """Mount every API router onto the given FastAPI app.

    Order matches the historical `server.py` registration order so any
    route-matching precedence baked into existing tests is preserved.
    """
    # Auth + identity
    from .auth import router as auth_router
    from .auth_extras import router as auth_extras_router
    from .contact import router as contact_router, admin_router as contact_admin_router
    from .user_profile import router as user_profile_router
    from .meta import router as meta_router

    # Marketing / engagement
    from .campaigns import router as campaigns_router
    from .ai import router as ai_router
    from .analytics import router as analytics_router
    from .beta_feedback import router as beta_feedback_router

    # Tenant + workspace
    from .pietential import router as pietential_router
    from .tenants import router as tenants_router

    # Billing
    from .billing import router as billing_router, webhook_router as stripe_webhook_router
    from .billing_plans import router as billing_plans_router
    from .billing_upgrade import router as billing_upgrade_router
    from .billing_profile import router as billing_profile_router

    # Touchpoints / engine
    from .touchpoints import router as touchpoints_router
    from .touchpoint_preview import router as touchpoint_preview_router
    from .touchpoint_engine import router as touchpoint_engine_router

    # Compliance / classification
    from .compliance import router as compliance_router
    from .contacts import router as contacts_router
    from .classification import router as classification_router
    from .aria_confidence import router as aria_confidence_router

    # Admin
    from .admin_revenue import router as admin_revenue_router, invoice_router as admin_invoice_router
    from .admin_deployments import router as admin_deployments_router
    from .audit_log import (
        router as audit_log_router,
        admin_router as admin_workspaces_router,
        admin_audit_router,
    )
    from .data_deletion import router as data_deletion_router
    from .reports import router as reports_router

    # CRM / lifecycle
    from .crm_sync import router as crm_sync_router

    # Capture + hub
    from .lead_capture import (
        router as lead_capture_router,
        public_router as lead_capture_public_router,
        widget_public_router as lead_capture_widget_public_router,
    )
    from .integrations_hub import (
        router as integrations_hub_router,
        public_router as integrations_hub_public_router,
    )
    from .outreach_import import router as outreach_import_router

    # Conversations / notifications
    from .conversations import router as conversations_router
    from .notifications import router as notifications_router

    # ICPs / outreach
    from .icps import router as icps_router
    from .outreach import router as outreach_router
    from .aria_auto_map import router as aria_auto_map_router

    # Catalog / channels / simulate
    from .integrations_catalog import router as integrations_catalog_router
    from .sales_channels import router as sales_channels_router
    from .simulate_inbound import router as simulate_inbound_router

    # Health / failures
    from .health_engine import (
        router as health_router,
        failed_router as failed_messages_router,
    )

    # Aria training (v2 master prompt — iter92)
    from .aria_training import router as aria_training_router

    # Pietential B2B Insights Engine (iter94 — Phase 3)
    from .pt_insights import router as pt_insights_router

    # Admin Dashboard v3 (iter95 — PART D)
    from .admin_v3 import router as admin_v3_router

    # Iter99 — Missing V3 lead integrations (Google Ads URL gen, Apollo
    # direct pull, Serper enrichment, Website Pixel snippet + tracker)
    from .integrations_extras import (
        router as integrations_extras_router,
        public_router as integrations_extras_public_router,
    )

    # Iter100 — Aria Resource Library (CRUD + upload + lead matcher)
    from .aria_resources import router as aria_resources_router

    # Iter101 — Visual Automation Rule Builder
    from .automation_rules import router as automation_rules_router

    # Iter103 — CSV lead import + Real-time polling + Onboarding state
    from .leads_csv import router as leads_csv_router
    from .realtime_onboarding import router as realtime_onboarding_router

    # Iter105 — P2 fixes batched (PDF, history/restore, URL scrape,
    # insights_enabled, admin job trigger, reports icp/channels, sequences,
    # WhatsApp command parser helper).
    from .iter105_fixes import router as iter105_fixes_router

    # Iter105 — Task 2: Insight Digest daily email
    from .insight_digest import router as insight_digest_router

    # Iter106 — ACTION 5: OAuth scaffolds (Calendly, Gmail, Outlook, Meta, LinkedIn, Google Ads)
    from .oauth_integrations import router as oauth_integrations_router

    # Iter108 — ACTION 2: real-time API key pre-validation (single endpoint, 6 providers)
    from .api_key_validator import router as api_key_validator_router

    # Iter108 — ACTION 3: server.py refactor — extracted self-contained endpoints
    from .assets_routes import router as assets_router
    from .webhooks_inbound import router as webhooks_inbound_router
    from .aria_eod_wrap import router as aria_eod_wrap_router
    from .webhooks_whatsapp import router as webhooks_whatsapp_router
    from .billing_plans_legacy import router as billing_plans_legacy_router
    from .lead_magnets import router as lead_magnets_router
    from .aria_call_priority import router as aria_call_priority_router
    from .demo_seeder import router as demo_seeder_router

    # Iter109 Batch 2 — Command Center KPIs (mode-aware aggregates)
    from .command_center import router as command_center_router

    # Iter109c Batch 1 — Universal OAuth providers (per-tenant credentials)
    from .oauth_providers import router as oauth_providers_router, public_router as oauth_providers_public_router

    # ─── Registration order preserved from legacy server.py ──────────────
    for router in (
        auth_router, auth_extras_router,
        contact_router, contact_admin_router,
        user_profile_router, meta_router,
        campaigns_router, ai_router, analytics_router, beta_feedback_router,
        pietential_router, tenants_router,
        billing_router, stripe_webhook_router,
        touchpoints_router, touchpoint_preview_router, touchpoint_engine_router,
        billing_plans_router, compliance_router, contacts_router,
        classification_router, aria_confidence_router,
        admin_revenue_router, admin_deployments_router, admin_invoice_router,
        crm_sync_router,
        audit_log_router, admin_workspaces_router, admin_audit_router,
        data_deletion_router, reports_router,
        lead_capture_router, lead_capture_public_router, lead_capture_widget_public_router,
        integrations_hub_router, integrations_hub_public_router,
        integrations_extras_router,
        integrations_extras_public_router,
        outreach_import_router,
        conversations_router, notifications_router,
        icps_router, outreach_router, aria_auto_map_router,
        billing_upgrade_router, billing_profile_router,
        integrations_catalog_router, sales_channels_router, simulate_inbound_router,
        health_router, failed_messages_router,
        aria_training_router,
        pt_insights_router,
        admin_v3_router,
        # iter109c — register universal OAuth providers FIRST so its handlers
        # win over the legacy provider-specific oauth_integrations_router for
        # the shared paths (/configure, /callback, /, /status).
        oauth_providers_router,
        oauth_providers_public_router,
        aria_resources_router,
        automation_rules_router,
        leads_csv_router,
        realtime_onboarding_router,
        iter105_fixes_router,
        insight_digest_router,
        oauth_integrations_router,
        api_key_validator_router,
        assets_router,
        webhooks_inbound_router,
        aria_eod_wrap_router,
        webhooks_whatsapp_router,
        billing_plans_legacy_router,
        lead_magnets_router,
        aria_call_priority_router,
        demo_seeder_router,
        command_center_router,
    ):
        app.include_router(router)
