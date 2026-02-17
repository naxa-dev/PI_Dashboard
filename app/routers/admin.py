"""
Admin router for sqlite backend.

Provides endpoints to view snapshots and upload new snapshot files.
"""

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ..db import get_connection
from ..services.snapshot_importer import import_snapshot
from ..schemas import SnapshotBase, SnapshotReport

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


@router.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, conn = Depends(get_conn)):
    """Render the admin page with snapshots list and upload form."""
    snapshots = conn.execute("SELECT * FROM snapshots ORDER BY snapshot_date DESC").fetchall()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "snapshots": snapshots,
        "body_class": "cockpit"
    })


@router.post("/admin/upload", response_class=HTMLResponse)
async def upload_snapshot(request: Request, files: list[UploadFile] = File(...), conn = Depends(get_conn)):
    """Handle snapshot upload (supports multiple files)."""
    
    aggregated_report = SnapshotReport(
        success=True,
        message="",
        processed_projects=0,
        processed_events=0,
        warnings=[],
        errors=[]
    )
    
    valid_files_count = 0
    
    for file in files:
        report = import_snapshot(file)
        aggregated_report.processed_projects += report.processed_projects
        aggregated_report.processed_events += report.processed_events
        
        prefix = f"[{file.filename}] "
        if report.warnings:
            aggregated_report.warnings.extend([prefix + w for w in report.warnings])
        if report.errors:
            aggregated_report.errors.extend([prefix + e for e in report.errors])
            aggregated_report.success = False # One failure marks overall false, or we can keep it mixed.
            # Let's keep success=True only if ALL succeed? 
            # Actually, let's allow partial success but show errors.
        
        if report.success:
            valid_files_count += 1

    # Final message construction
    if aggregated_report.errors:
        aggregated_report.success = False
        aggregated_report.message = f"Processed {len(files)} files. {valid_files_count} succeeded, {len(files)-valid_files_count} failed."
    else:
        aggregated_report.success = True
        aggregated_report.message = f"Successfully uploaded {valid_files_count} files."

    snapshots = conn.execute("SELECT * FROM snapshots ORDER BY snapshot_date DESC").fetchall()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "snapshots": snapshots,
        "report": aggregated_report,
        "body_class": "cockpit"
    })


@router.get("/api/snapshots", response_class=JSONResponse)
def list_snapshots(conn = Depends(get_conn)):
    """Return snapshots as JSON."""
    rows = conn.execute("SELECT * FROM snapshots ORDER BY snapshot_date DESC").fetchall()
    data = []
    for row in rows:
        data.append({
            "snapshot_id": row["snapshot_id"],
            "snapshot_date": row["snapshot_date"],
            "uploaded_at": row["uploaded_at"],
            "source_filename": row["source_filename"],
        })
    return data