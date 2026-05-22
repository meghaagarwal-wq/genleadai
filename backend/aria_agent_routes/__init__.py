"""aria_agent_routes package — exposes attach_aria_agent_routes for server.py.

Routes were extracted into per-feature submodules in iter75. Importing each
submodule registers its decorators on the shared router defined in _shared.
"""
from ._shared import router  # noqa: F401  — shared router

# Import all feature submodules so their @router decorators register.
from . import training      # noqa: F401
from . import playbooks     # noqa: F401
from . import journeys      # noqa: F401
from . import briefs        # noqa: F401
from . import workspace     # noqa: F401
from . import handoff       # noqa: F401
from . import revival       # noqa: F401
from . import agent_activity  # noqa: F401
from . import insights      # noqa: F401
from . import assets        # noqa: F401
from . import brain         # noqa: F401
from . import weekly_recap  # noqa: F401
from . import health        # noqa: F401
from . import suggested_assets  # noqa: F401


def attach_aria_agent_routes(app, get_current_user=None, db=None):
    """Compatibility shim. Routes live in submodules; this just includes the
    router on the supplied app. Legacy positional args are accepted & ignored.
    """
    app.include_router(router)
