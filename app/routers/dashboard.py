"""Dashboard router for sqlite backend.

Renders the main cockpit-style dashboard page with metrics and tables.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..db import get_connection
from ..services import metrics as metrics_service

router = APIRouter()

# Determine absolute template directory based on this file location.
templates = Jinja2Templates(directory=str((Path(__file__).resolve().parent.parent) / "templates"))


def get_conn():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    snapshot_id: int = Query(None),
    month: str = Query(None),
    filter_champion: str = Query(None),
    filter_strategy: str = Query(None),
    filter_status: str = Query("승인(진행중)"),
    sort: str = Query(None),
    order: str = Query("asc"),
    rank_sort: str = Query("count"),
    rank_order: str = Query("desc"),
    conn=Depends(get_conn),
):
    """Render dashboard page."""

    # Fetch snapshots list
    snapshots = conn.execute("SELECT * FROM snapshots ORDER BY snapshot_date DESC").fetchall()
    if not snapshots:
        return templates.TemplateResponse(
            "dashboard.html",
            {"request": request, "snapshots": [], "message": "No snapshots available."},
        )

    # Determine snapshot
    selected_snapshot = None
    if snapshot_id:
        for s in snapshots:
            if s["snapshot_id"] == snapshot_id:
                selected_snapshot = s
                break
    if not selected_snapshot:
        selected_snapshot = snapshots[0]

    # Determine months
    months = metrics_service.get_snapshot_months(conn, selected_snapshot["snapshot_id"])
    selected_month = month if (month and month in months) else (months[0] if months else None)

    # Compute metrics and heatmap
    kpis = proposal_ranking = approval_ranking = active_ranking = distribution = heatmap = None
    max_prop = max_app = 0
    trend = {"months": [], "proposals": [], "approvals": []}
    status_dist = []
    active_by_strategy = []

    # 신규 제안(월) 전략분류 비중
    monthly_prop_strat = []

    if selected_month:
        kpis = metrics_service.compute_kpis(conn, selected_snapshot["snapshot_id"], selected_month)
        proposal_ranking, approval_ranking, active_ranking = metrics_service.compute_ranking(
            conn, selected_snapshot["snapshot_id"], selected_month, rank_sort, rank_order
        )
        distribution = metrics_service.compute_distribution(conn, selected_snapshot["snapshot_id"], selected_month)
        heatmap = metrics_service.compute_heatmap(conn, selected_snapshot["snapshot_id"])
        trend = metrics_service.compute_monthly_trend(conn, selected_snapshot["snapshot_id"])
        status_dist = metrics_service.compute_status_distribution(conn, selected_snapshot["snapshot_id"])
        active_by_strategy = metrics_service.compute_active_by_strategy(conn, selected_snapshot["snapshot_id"])
        monthly_prop_strat = metrics_service.compute_monthly_proposals_share_by_strategy(
            conn, selected_snapshot["snapshot_id"], selected_month
        )

        # Compute maxima for heatmap
        for months_data in heatmap.values():
            for cell in months_data.values():
                if cell["proposals"] > max_prop:
                    max_prop = cell["proposals"]
                if cell["approvals"] > max_app:
                    max_app = cell["approvals"]

    # Projects list (dashboard priority): champion-grouped view of projects.
    active_projects = []
    if selected_month:
        base_query = """
            SELECT p.project_id, p.project_name, p.current_status,
                   c.name AS champion_name, s.name AS strategy_name,
                   p.champion_id, p.strategy_id
            FROM projects p
            LEFT JOIN champions c ON p.champion_id = c.champion_id
            LEFT JOIN strategy_categories s ON p.strategy_id = s.strategy_id
            WHERE p.snapshot_id = ?
        """
        params = [selected_snapshot["snapshot_id"]]

        if filter_status:
            base_query += " AND p.current_status = ?"
            params.append(filter_status)

        if filter_champion:
            if filter_champion == "(미할당)":
                base_query += " AND p.champion_id IS NULL"
            else:
                base_query += " AND c.name = ?"
                params.append(filter_champion)

        if filter_strategy:
            if filter_strategy == "(미할당)":
                base_query += " AND p.strategy_id IS NULL"
            else:
                base_query += " AND s.name = ?"
                params.append(filter_strategy)

        # Sorting logic
        sort_map = {
            "project_id": "p.project_id",
            "project_name": "p.project_name",
            "champion": "c.name",
            "strategy": "s.name",
            "status": "p.current_status"
        }
        
        # Default sort
        order_clause = "ORDER BY c.name IS NULL, c.name, p.project_name"

        if sort and sort in sort_map:
            direction = "DESC" if order == "desc" else "ASC"
            # Special handling for NULLs if needed, generally standard sort is fine
            order_clause = f"ORDER BY {sort_map[sort]} {direction}"
        
        base_query += f" {order_clause}"
        active_projects = conn.execute(base_query, params).fetchall()

    # Distribution arrays for chart
    dist_labels: list[str] = []
    proposals_data: list[int] = []
    approvals_data: list[int] = []
    active_data: list[int] = []
    if distribution:
        for row in distribution:
            dist_labels.append(row[0])
            proposals_data.append(row[1])
            approvals_data.append(row[2])
            active_data.append(row[3])

    # Proposal share by strategy arrays
    prop_strat_labels: list[str] = [x[0] for x in monthly_prop_strat]
    prop_strat_values: list[int] = [x[1] for x in monthly_prop_strat]
    prop_strat_shares: list[float] = [round(x[2] * 100, 1) for x in monthly_prop_strat]

    # Build Top-N arrays for charts
    top_n = 10
    top_prop_labels = [x[0] for x in (proposal_ranking or [])[:top_n]]
    top_prop_values = [x[1] for x in (proposal_ranking or [])[:top_n]]
    top_app_labels = [x[0] for x in (approval_ranking or [])[:top_n]]
    top_app_values = [x[1] for x in (approval_ranking or [])[:top_n]]

    status_labels = [x[0] for x in status_dist]
    status_values = [x[1] for x in status_dist]

    active_strat_labels = [x[0] for x in (active_by_strategy or [])]
    active_strat_values = [x[1] for x in (active_by_strategy or [])]

    # Strategy bias warning: any strategy taking >= 50% of total active
    bias_strategy = None
    bias_ratio = 0.0
    total_active_cnt = sum(active_strat_values) if active_strat_values else 0
    if total_active_cnt > 0:
        for name, cnt in zip(active_strat_labels, active_strat_values):
            r = cnt / total_active_cnt
            if r >= 0.5 and r > bias_ratio:
                bias_strategy = name
                bias_ratio = r

    context = {
        "request": request,
        "title": "AX Operations Cockpit",
        "body_class": "cockpit",
        "snapshots": snapshots,
        "snapshot": selected_snapshot,
        "months": months,
        "selected_month": selected_month,
        "kpis": kpis,
        "proposal_ranking": proposal_ranking,
        "approval_ranking": approval_ranking,
        "active_ranking": active_ranking,
        "distribution": distribution,
        "dist_labels": dist_labels,
        "proposals_data": proposals_data,
        "approvals_data": approvals_data,
        "active_data": active_data,
        "trend_months": trend.get("months", []),
        "trend_proposals": trend.get("proposals", []),
        "trend_approvals": trend.get("approvals", []),
        "top_prop_labels": top_prop_labels,
        "top_prop_values": top_prop_values,
        "top_app_labels": top_app_labels,
        "top_app_values": top_app_values,
        "status_labels": status_labels,
        "status_values": status_values,
        "active_strat_labels": active_strat_labels,
        "active_strat_values": active_strat_values,
        "bias_strategy": bias_strategy,
        "bias_ratio": round(bias_ratio * 100, 1) if bias_strategy else 0,
        "heatmap": heatmap,
        "active_projects": active_projects,
        "selected_champion": filter_champion,
        "selected_strategy": filter_strategy,
        "selected_status": filter_status,
        "max_prop": max_prop,
        "max_app": max_app,
        # 신규제안(월) 전략분류 분포
        "prop_strat_labels": prop_strat_labels,
        "prop_strat_values": prop_strat_values,
        "prop_strat_shares": prop_strat_shares,
        "current_sort": sort,
        "current_order": order,
        "current_rank_sort": rank_sort,
        "current_rank_order": rank_order,
    }

    return templates.TemplateResponse("dashboard.html", context)
