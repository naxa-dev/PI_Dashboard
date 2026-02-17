"""
CRUD routes for project management using sqlite backend.

Allows listing and editing projects within a snapshot.
"""

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..db import get_connection
from ..services.audit import record_audit

router = APIRouter()
from pathlib import Path

# Determine absolute template directory based on this file location.  The
# `routers` package sits under `app/routers`, while templates live in
# `app/templates`.  Therefore we ascend one directory above the current
# file's directory and join the `templates` folder.  Using an absolute
# path avoids issues when FastAPI reloader changes the working directory.
templates = Jinja2Templates(directory=str((Path(__file__).resolve().parent.parent) / "templates"))


def get_conn():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/admin/projects", response_class=HTMLResponse)
def list_projects(request: Request, snapshot_id: int = None, conn = Depends(get_conn)):
    """List projects for a snapshot."""
    snapshots = conn.execute("SELECT * FROM snapshots ORDER BY snapshot_date DESC").fetchall()
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots available")
    selected_snapshot = None
    if snapshot_id:
        for s in snapshots:
            if s['snapshot_id'] == snapshot_id:
                selected_snapshot = s
                break
    if not selected_snapshot:
        selected_snapshot = snapshots[0]
    # Fetch projects with champion and strategy names
    projects = conn.execute(
        """
        SELECT p.*, c.name AS champion_name, s.name AS strategy_name
        FROM projects p
        LEFT JOIN champions c ON p.champion_id = c.champion_id
        LEFT JOIN strategy_categories s ON p.strategy_id = s.strategy_id
        WHERE p.snapshot_id = ?
        ORDER BY p.project_id
        """,
        (selected_snapshot['snapshot_id'],)
    ).fetchall()
    champions = conn.execute("SELECT * FROM champions ORDER BY name").fetchall()
    strategies = conn.execute("SELECT * FROM strategy_categories ORDER BY name").fetchall()
    return templates.TemplateResponse("crud_projects.html", {
        "request": request,
        "snapshots": snapshots,
        "snapshot": selected_snapshot,
        "projects": projects,
        "champions": champions,
        "strategies": strategies,
        "body_class": "cockpit"
    })


@router.get("/admin/projects/{snapshot_id}/{project_id}/edit", response_class=HTMLResponse)
def edit_project_form(request: Request, snapshot_id: int, project_id: str, conn = Depends(get_conn)):
    """Render the edit form for a project."""
    project = conn.execute(
        """
        SELECT * FROM projects WHERE snapshot_id = ? AND project_id = ?
        """,
        (snapshot_id, project_id)
    ).fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    champions = conn.execute("SELECT * FROM champions ORDER BY name").fetchall()
    strategies = conn.execute("SELECT * FROM strategy_categories ORDER BY name").fetchall()
    return templates.TemplateResponse("crud_projects.html", {
        "request": request,
        "edit_project": project,
        "champions": champions,
        "strategies": strategies,
        "snapshot_id": snapshot_id,
        "body_class": "cockpit"
    })


@router.post("/admin/projects/{snapshot_id}/{project_id}/edit")
def update_project(snapshot_id: int, project_id: str,
                   project_name: str = Form(...),
                   champion_id: int = Form(None),
                   strategy_id: int = Form(None),
                   org_unit: str = Form(None),
                   current_status: str = Form(...),
                   proposed_month: str = Form(None),
                   approved_month: str = Form(None),
                   conn = Depends(get_conn)):
    """Update a project and record audit."""
    # Fetch before
    before = conn.execute(
        "SELECT project_name, champion_id, strategy_id, org_unit, current_status, proposed_month, approved_month FROM projects WHERE snapshot_id = ? AND project_id = ?",
        (snapshot_id, project_id)
    ).fetchone()
    if not before:
        raise HTTPException(status_code=404, detail="Project not found")
    # Normalize empty champion/strategy as None
    champ_id = champion_id if champion_id not in (None, 0, '0', '') else None
    strat_id = strategy_id if strategy_id not in (None, 0, '0', '') else None
    conn.execute(
        """
        UPDATE projects SET project_name = ?, champion_id = ?, strategy_id = ?, org_unit = ?, current_status = ?, proposed_month = ?, approved_month = ?
        WHERE snapshot_id = ? AND project_id = ?
        """,
        (
            project_name,
            champ_id,
            strat_id,
            org_unit,
            current_status,
            proposed_month,
            approved_month,
            snapshot_id,
            project_id,
        )
    )
    conn.commit()
    # Fetch after
    after = conn.execute(
        "SELECT project_name, champion_id, strategy_id, org_unit, current_status, proposed_month, approved_month FROM projects WHERE snapshot_id = ? AND project_id = ?",
        (snapshot_id, project_id)
    ).fetchone()
    # Record audit
    record_audit(conn, snapshot_id, 'project', project_id, 'UPDATE', dict(before), dict(after), actor='admin')
    return RedirectResponse(url=f"/admin/projects?snapshot_id={snapshot_id}", status_code=303)