"""Metrics computation functions for sqlite backend.

Each function uses a provided sqlite3 connection to compute aggregations
needed for the dashboard. The connection must have row_factory set to
sqlite3.Row for dictionary-like row access.

Important principles
- Scoring is NOT used. Only simple counts and ratios derived from counts.
- Snapshot-scoped: all metrics are computed within a selected snapshot.
"""

from __future__ import annotations

from typing import List, Tuple, Dict

import sqlite3


def compute_monthly_trend(conn: sqlite3.Connection, snapshot_id: int) -> Dict[str, List]:
    """Return month list and totals for proposals/approvals."""
    months = get_snapshot_months(conn, snapshot_id)
    if not months:
        return {"months": [], "proposals": [], "approvals": []}

    c = conn.cursor()
    proposals: List[int] = []
    approvals: List[int] = []
    for m in months:
        c.execute(
            """
            SELECT
              SUM(CASE WHEN is_new_proposal = 1 THEN 1 ELSE 0 END) AS p_cnt,
              SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END) AS a_cnt
            FROM project_monthly_events
            WHERE snapshot_id = ? AND month_key = ?
            """,
            (snapshot_id, m),
        )
        row = c.fetchone()
        proposals.append(int(row[0] or 0))
        approvals.append(int(row[1] or 0))

    return {"months": months, "proposals": proposals, "approvals": approvals}


def compute_status_distribution(conn: sqlite3.Connection, snapshot_id: int) -> List[Tuple[str, int]]:
    """Count projects by current_status for a snapshot."""
    c = conn.cursor()
    c.execute(
        """
        SELECT current_status, COUNT(*) AS cnt
        FROM projects
        WHERE snapshot_id = ?
        GROUP BY current_status
        """,
        (snapshot_id,),
    )
    rows = [(row[0] or "(blank)", int(row[1] or 0)) for row in c.fetchall()]
    rows.sort(key=lambda x: -x[1])
    return rows


def compute_active_by_strategy(conn: sqlite3.Connection, snapshot_id: int) -> List[Tuple[str, int]]:
    """Count active projects by strategy category (snapshot scope)."""
    c = conn.cursor()
    c.execute("SELECT strategy_id, name FROM strategy_categories")
    strat_map = {row["strategy_id"]: row["name"] for row in c.fetchall()}
    strat_map[None] = "(미할당)"

    c.execute(
        """
        SELECT strategy_id AS sid, COUNT(*) AS cnt
        FROM projects
        WHERE snapshot_id = ? AND current_status = '승인(진행중)'
        GROUP BY strategy_id
        """,
        (snapshot_id,),
    )
    result = [(strat_map.get(row["sid"], "(미할당)"), int(row["cnt"] or 0)) for row in c.fetchall()]

    # Include zero counts for known categories (keeps chart stable)
    existing = {name for name, _ in result}
    for _, name in strat_map.items():
        if name not in existing:
            result.append((name, 0))

    result.sort(key=lambda x: (-x[1], x[0] or ""))
    return result


def get_snapshot_months(conn: sqlite3.Connection, snapshot_id: int) -> List[str]:
    c = conn.cursor()
    c.execute(
        "SELECT DISTINCT month_key FROM project_monthly_events WHERE snapshot_id = ?",
        (snapshot_id,),
    )
    months = [row[0] for row in c.fetchall()]
    months.sort()
    return months


def compute_kpis(conn: sqlite3.Connection, snapshot_id: int, month: str) -> Dict:
    """Compute KPI set for a snapshot + selected month.

    KPI 정의(요약)
    - 누적 승인 수(=해당 월 이하 승인 누적): events 기준 (month_key <= selected month)
    - 월 신규 제안 수: events 기준 (is_new_proposal=1)
    - 월 승인 수: events 기준 (is_approved=1)
    - Champion 참여율: 선택 월에 (제안+승인)>0 인 Champion 수 / 전체 Champion 수
    - 과제 추진 확대율: (지난달 누적 승인 + 금월 승인) / 지난달 누적 승인
      = (금월 누적 승인) / (지난달 누적 승인)
    - 신규 과제 제안 유입률: (월 신규 제안 수) / (월 승인 수)
      * "금번 달 진행 건수"를 월 승인 수로 해석 (승인=진행 착수 트리거)
    """

    c = conn.cursor()

    # 월 신규 제안
    c.execute(
        """
        SELECT COUNT(*)
        FROM project_monthly_events
        WHERE snapshot_id = ? AND month_key = ? AND is_new_proposal = 1
        """,
        (snapshot_id, month),
    )
    month_proposals = int(c.fetchone()[0] or 0)

    # 월 승인
    c.execute(
        """
        SELECT COUNT(*)
        FROM project_monthly_events
        WHERE snapshot_id = ? AND month_key = ? AND is_approved = 1
        """,
        (snapshot_id, month),
    )
    month_approvals = int(c.fetchone()[0] or 0)

    # 누적 승인(해당 월 이하) - DISTINCT project
    c.execute(
        """
        SELECT COUNT(DISTINCT project_id) AS cnt
        FROM project_monthly_events
        WHERE snapshot_id = ? AND month_key <= ? AND is_approved = 1
        """,
        (snapshot_id, month),
    )
    cumulative_approved = int(c.fetchone()[0] or 0)

    # Champion 참여율
    c.execute(
        """
        SELECT COUNT(DISTINCT champion_id)
        FROM project_monthly_events
        WHERE snapshot_id = ? AND month_key = ? AND (is_new_proposal = 1 OR is_approved = 1)
        """,
        (snapshot_id, month),
    )
    active_champions = int(c.fetchone()[0] or 0)

    c.execute(
        "SELECT COUNT(DISTINCT champion_id) FROM projects WHERE snapshot_id = ?",
        (snapshot_id,),
    )
    total_champions = int(c.fetchone()[0] or 0)
    participation_rate = (active_champions / total_champions) if total_champions else 0.0

    # 지난달 누적 승인(확대율 계산용)
    months = get_snapshot_months(conn, snapshot_id)
    prev_month = None
    if month in months:
        idx = months.index(month)
        if idx > 0:
            prev_month = months[idx - 1]

    prev_cumulative = 0
    if prev_month:
        c.execute(
            """
            SELECT COUNT(DISTINCT project_id) AS cnt
            FROM project_monthly_events
            WHERE snapshot_id = ? AND month_key <= ? AND is_approved = 1
            """,
            (snapshot_id, prev_month),
        )
        prev_cumulative = int(c.fetchone()[0] or 0)

    # 과제 추진 확대율
    expansion_rate = (cumulative_approved / prev_cumulative) if prev_cumulative else 0.0

    # 신규 과제 제안 유입률
    proposal_inflow_rate = (month_proposals / month_approvals) if month_approvals else 0.0

    return {
        "month_proposals": month_proposals,
        "month_approvals": month_approvals,
        "cumulative_approved": cumulative_approved,
        "champion_participation_rate": round(participation_rate, 4),
        "expansion_rate": round(expansion_rate, 4),
        "proposal_inflow_rate": round(proposal_inflow_rate, 4),
        # for display/debug
        "prev_month": prev_month,
        "prev_cumulative_approved": prev_cumulative,
    }


def compute_ranking(
    conn: sqlite3.Connection, snapshot_id: int, month: str, rank_sort: str = "count", rank_order: str = "desc"
) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]], List[Tuple[str, int]]]:
    c = conn.cursor()
    c.execute("SELECT champion_id, name FROM champions")
    champ_map = {row["champion_id"]: row["name"] for row in c.fetchall()}
    champ_map[None] = "(미할당)"

    # Proposals
    c.execute(
        """
        SELECT champion_id, COUNT(*) AS cnt
        FROM project_monthly_events
        WHERE snapshot_id = ? AND month_key = ? AND is_new_proposal = 1
        GROUP BY champion_id
        """,
        (snapshot_id, month),
    )
    proposal_counts = {row["champion_id"]: int(row["cnt"] or 0) for row in c.fetchall()}

    # Approvals
    c.execute(
        """
        SELECT champion_id, COUNT(*) AS cnt
        FROM project_monthly_events
        WHERE snapshot_id = ? AND month_key = ? AND is_approved = 1
        GROUP BY champion_id
        """,
        (snapshot_id, month),
    )
    approval_counts = {row["champion_id"]: int(row["cnt"] or 0) for row in c.fetchall()}

    # Active (projects table)
    c.execute(
        """
        SELECT champion_id, COUNT(*) AS cnt
        FROM projects
        WHERE snapshot_id = ? AND current_status = '승인(진행중)'
        GROUP BY champion_id
        """,
        (snapshot_id,),
    )
    active_counts = {row["champion_id"]: int(row["cnt"] or 0) for row in c.fetchall()}

    proposal_ranking = [(champ_map.get(cid), count) for cid, count in proposal_counts.items()]
    approval_ranking = [(champ_map.get(cid), count) for cid, count in approval_counts.items()]
    active_ranking = [(champ_map.get(cid), count) for cid, count in active_counts.items()]

    proposal_ranking.sort(key=lambda x: (-x[1], x[0] or ""))
    approval_ranking.sort(key=lambda x: (-x[1], x[0] or ""))
    active_ranking.sort(key=lambda x: (-x[1], x[0] or ""))

    # Ranking Sort Logic
    if rank_sort == "champion":
        # Sort by Name
        reverse = (rank_order == "desc")
        active_ranking.sort(key=lambda x: x[0] or "", reverse=reverse)
    else:
        # Default: Sort by Count (desc default)
        # If rank_sort is 'count' or None
        reverse = (rank_order == "desc")
        # Primary: Count, Secondary: Name
        # Note: If sorting by count ASC, we want low counts first.
        # If sorting by count DESC, we want high counts first.
        if reverse:
              active_ranking.sort(key=lambda x: (-x[1], x[0] or ""))
        else:
             active_ranking.sort(key=lambda x: (x[1], x[0] or ""))

    return proposal_ranking, approval_ranking, active_ranking


def compute_distribution(conn: sqlite3.Connection, snapshot_id: int, month: str) -> List[Tuple[str, int, int, int]]:
    c = conn.cursor()
    c.execute("SELECT strategy_id, name FROM strategy_categories")
    strat_map = {row["strategy_id"]: row["name"] for row in c.fetchall()}
    strat_map[None] = "(미할당)"

    distribution: Dict[int, Dict[str, int]] = {}
    for sid in strat_map.keys():
        distribution[sid] = {"proposals": 0, "approvals": 0, "active": 0}

    # Proposals
    c.execute(
        """
        SELECT p.strategy_id AS sid, COUNT(*) AS cnt
        FROM project_monthly_events AS e
        JOIN projects AS p
          ON e.snapshot_id = p.snapshot_id AND e.project_id = p.project_id
        WHERE e.snapshot_id = ? AND e.month_key = ? AND e.is_new_proposal = 1
        GROUP BY p.strategy_id
        """,
        (snapshot_id, month),
    )
    for row in c.fetchall():
        distribution[row["sid"]]["proposals"] = int(row["cnt"] or 0)

    # Approvals
    c.execute(
        """
        SELECT p.strategy_id AS sid, COUNT(*) AS cnt
        FROM project_monthly_events AS e
        JOIN projects AS p
          ON e.snapshot_id = p.snapshot_id AND e.project_id = p.project_id
        WHERE e.snapshot_id = ? AND e.month_key = ? AND e.is_approved = 1
        GROUP BY p.strategy_id
        """,
        (snapshot_id, month),
    )
    for row in c.fetchall():
        distribution[row["sid"]]["approvals"] = int(row["cnt"] or 0)

    # Active
    c.execute(
        """
        SELECT strategy_id AS sid, COUNT(*) AS cnt
        FROM projects
        WHERE snapshot_id = ? AND current_status = '승인(진행중)'
        GROUP BY strategy_id
        """,
        (snapshot_id,),
    )
    for row in c.fetchall():
        distribution[row["sid"]]["active"] = int(row["cnt"] or 0)

    result = []
    for sid, vals in distribution.items():
        result.append((strat_map[sid], vals["proposals"], vals["approvals"], vals["active"]))

    result.sort(key=lambda x: x[0] or "")
    return result


def compute_monthly_proposals_share_by_strategy(
    conn: sqlite3.Connection, snapshot_id: int, month: str
) -> List[Tuple[str, int, float]]:
    """월 신규 제안 과제의 전략분류별 분포(비중 포함).

    Returns: [(strategy_name, proposal_count, share_float_0_1), ...]
    """
    c = conn.cursor()
    c.execute("SELECT strategy_id, name FROM strategy_categories")
    strat_map = {row["strategy_id"]: row["name"] for row in c.fetchall()}
    strat_map[None] = "(미할당)"

    c.execute(
        """
        SELECT p.strategy_id AS sid, COUNT(*) AS cnt
        FROM project_monthly_events AS e
        JOIN projects AS p
          ON e.snapshot_id = p.snapshot_id AND e.project_id = p.project_id
        WHERE e.snapshot_id = ?
          AND e.month_key = ?
          AND e.is_new_proposal = 1
        GROUP BY p.strategy_id
        """,
        (snapshot_id, month),
    )
    rows = [(row["sid"], int(row["cnt"] or 0)) for row in c.fetchall()]
    total = sum(cnt for _, cnt in rows) or 0

    result: List[Tuple[str, int, float]] = []
    for sid, cnt in rows:
        name = strat_map.get(sid, "(미할당)")
        share = (cnt / total) if total else 0.0
        result.append((name, cnt, share))

    result.sort(key=lambda x: (-x[1], x[0] or ""))
    return result


def compute_heatmap(conn: sqlite3.Connection, snapshot_id: int) -> Dict[str, Dict[str, Dict[str, int]]]:
    c = conn.cursor()
    c.execute("SELECT champion_id, name FROM champions")
    champ_map = {row["champion_id"]: row["name"] for row in c.fetchall()}
    champ_map[None] = "(미할당)"

    months = get_snapshot_months(conn, snapshot_id)

    heatmap: Dict[str, Dict[str, Dict[str, int]]] = {}
    for _, cname in champ_map.items():
        heatmap[cname] = {m: {"proposals": 0, "approvals": 0} for m in months}

    # proposals
    c.execute(
        """
        SELECT champion_id, month_key, COUNT(*) AS cnt
        FROM project_monthly_events
        WHERE snapshot_id = ? AND is_new_proposal = 1
        GROUP BY champion_id, month_key
        """,
        (snapshot_id,),
    )
    for row in c.fetchall():
        cname = champ_map.get(row["champion_id"])
        if cname and row["month_key"] in heatmap[cname]:
            heatmap[cname][row["month_key"]]["proposals"] = int(row["cnt"] or 0)

    # approvals
    c.execute(
        """
        SELECT champion_id, month_key, COUNT(*) AS cnt
        FROM project_monthly_events
        WHERE snapshot_id = ? AND is_approved = 1
        GROUP BY champion_id, month_key
        """,
        (snapshot_id,),
    )
    for row in c.fetchall():
        cname = champ_map.get(row["champion_id"])
        if cname and row["month_key"] in heatmap[cname]:
            heatmap[cname][row["month_key"]]["approvals"] = int(row["cnt"] or 0)

    return heatmap
