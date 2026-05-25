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
        outreach_import_router,
        conversations_router, notifications_router,
        icps_router, outreach_router, aria_auto_map_router,
        billing_upgrade_router, billing_profile_router,
        integrations_catalog_router, sales_channels_router, simulate_inbound_router,
        health_router, failed_messages_router,
    ):
        app.include_router(router)
