"""
CRUD routes for monthly events using sqlite backend.

Lists and updates project monthly events for a given snapshot and month.
"""

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..db import get_connection
from ..services.metrics import get_snapshot_months
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


@router.get("/admin/events", response_class=HTMLResponse)
def list_events(request: Request, snapshot_id: int = None, month: str = None, conn = Depends(get_conn)):
    """List monthly events for a snapshot and month."""
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
    months = get_snapshot_months(conn, selected_snapshot['snapshot_id'])
    selected_month = month if (month and month in months) else (months[0] if months else None)
    events = []
    if selected_month:
        events = conn.execute(
            """
            SELECT e.*, c.name AS champion_name
            FROM project_monthly_events e
            LEFT JOIN champions c ON e.champion_id = c.champion_id
            WHERE e.snapshot_id = ? AND e.month_key = ?
            ORDER BY e.project_id
            """,
            (selected_snapshot['snapshot_id'], selected_month)
        ).fetchall()
    champions = conn.execute("SELECT * FROM champions ORDER BY name").fetchall()
    return templates.TemplateResponse("crud_events.html", {
        "request": request,
        "snapshots": snapshots,
        "snapshot": selected_snapshot,
        "months": months,
        "selected_month": selected_month,
        "events": events,
        "champions": champions,
        "body_class": "cockpit"
    })


@router.post("/admin/events/{snapshot_id}/{month}/{project_id}/edit")
def update_event(snapshot_id: int, month: str, project_id: str,
                 champion_id: int = Form(None),
                 is_new_proposal: str = Form(None),
                 is_approved: str = Form(None),
                 note: str = Form(None),
                 conn = Depends(get_conn)):
    """Update a monthly event and record audit."""
    # Retrieve existing event
    before = conn.execute(
        "SELECT champion_id, is_new_proposal, is_approved, note FROM project_monthly_events WHERE snapshot_id = ? AND month_key = ? AND project_id = ?",
        (snapshot_id, month, project_id)
    ).fetchone()
    if not before:
        raise HTTPException(status_code=404, detail="Event not found")
    # Normalise booleans: HTML sends 'true' when checked
    new_flag = 1 if is_new_proposal else 0
    approved_flag = 1 if is_approved else 0
    champ_id = champion_id if champion_id not in (None, 0, '0', '') else None
    conn.execute(
        """
        UPDATE project_monthly_events
        SET champion_id = ?, is_new_proposal = ?, is_approved = ?, note = ?
        WHERE snapshot_id = ? AND month_key = ? AND project_id = ?
        """,
        (champ_id, new_flag, approved_flag, note, snapshot_id, month, project_id)
    )
    conn.commit()
    after = conn.execute(
        "SELECT champion_id, is_new_proposal, is_approved, note FROM project_monthly_events WHERE snapshot_id = ? AND month_key = ? AND project_id = ?",
        (snapshot_id, month, project_id)
    ).fetchone()
    # Audit
    record_audit(conn, snapshot_id, 'event', f"{month}|{project_id}", 'UPDATE', dict(before), dict(after), actor='admin')
    return RedirectResponse(url=f"/admin/events?snapshot_id={snapshot_id}&month={month}", status_code=303)