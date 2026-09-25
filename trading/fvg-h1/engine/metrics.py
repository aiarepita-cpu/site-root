from .models import Trade


def summarize(trades: list[Trade]) -> dict:
    closed = [t for t in trades if t.outcome is not None]
    open_ = [t for t in trades if t.outcome is None]
    n = len(closed)
    if n == 0:
        return {"total_trades": len(trades), "closed_trades": 0, "still_open": len(open_)}

    wins = [t for t in closed if t.outcome == "TP"]
    losses = [t for t in closed if t.outcome == "SL"]
    r_series = [(t.rr if t.outcome == "TP" else -1.0) for t in closed]
    equity_r = []
    running = 0.0
    for r in r_series:
        running += r
        equity_r.append(running)
    peak = float("-inf")
    max_dd = 0.0
    for e in equity_r:
        peak = max(peak, e)
        max_dd = max(max_dd, peak - e)

    gross_win_r = sum(r for r in r_series if r > 0)
    gross_loss_r = -sum(r for r in r_series if r < 0)

    return {
        "total_trades": len(trades),
        "closed_trades": n,
        "still_open": len(open_),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(100 * len(wins) / n, 2),
        "avg_rr_planned": round(sum(t.rr for t in closed) / n, 3),
        "avg_rr_winners": round(sum(t.rr for t in wins) / len(wins), 3) if wins else None,
        "expectancy_R": round(sum(r_series) / n, 3),
        "net_R": round(sum(r_series), 3),
        "profit_factor": round(gross_win_r / gross_loss_r, 3) if gross_loss_r > 0 else None,
        "max_drawdown_R": round(max_dd, 3),
    }
