"""
Plugins router — list available action plugins.
"""
from fastapi import APIRouter, Depends

from ..services.auth import get_current_user
from ..services.plugin_manager import list_plugins

router = APIRouter(prefix="/api/v1", tags=["plugins"])


@router.get("/plugins")
def get_plugins(current_user=Depends(get_current_user)):
    """Return list of all registered plugins and their supported actions."""
    return {"plugins": list_plugins()}
