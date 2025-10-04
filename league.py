from datetime import date, timedelta
from collections import defaultdict

def seed():
    return {"sessions":0,"active_days":0,"run_km":0.0,"strength_sessions":0,"swim_m":0,"other_sessions":0,"rest_days":0}

def month_bounds(d: date):
    start = d.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year+1, month=1, day=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month+1, day=1) - timedelta(days=1)
    return start, end

def compute_month_totals(state: dict, month_start: date):
    start, end = month_bounds(month_start)
    days_in_month = (end - start).days + 1
    totals = defaultdict(seed)
    cur = start
    while cur <= end:
        key = cur.isoformat()
        for a in state.get("activities", {}).get(key, []):
            p = a["phone"]
            t = totals[p]
            t["sessions"] += 1
            if a["type"] == "run": t["run_km"] += float(a.get("metrics",{}).get("km", 0))
            elif a["type"] == "strength": t["strength_sessions"] += 1
            elif a["type"] == "swim": t["swim_m"] += int(a.get("metrics",{}).get("m", 0))
            else: t["other_sessions"] += 1
            t["active_days"] += 0  # marcado por dia mais abaixo
        # marcar active_days por usuário que treinou no dia
        seen = {a["phone"] for a in state.get("activities", {}).get(key, [])}
        for p in seen: totals[p]["active_days"] += 1
        cur += timedelta(days=1)

    # include users sem treino
    for p in (state.get("users") or {}):
        _ = totals[p]  # força criação
    for p, t in totals.items():
        t["rest_days"] = days_in_month - t["active_days"]
    return dict(totals)

def pick_winners(totals: dict):
    arr = [{"phone":p, **t} for p,t in totals.items()]
    def mx(k, ties=None):
        ties = ties or []
        arr.sort(key=lambda x: (x[k], *[x[t] for t in ties]), reverse=True)
        return arr[0]["phone"] if arr else None
    return {
        "overall": mx("active_days", ["sessions","run_km"]),
        "run": mx("run_km", ["active_days"]),
        "strength": mx("strength_sessions", ["active_days"]),
        "swim": mx("swim_m", ["active_days"]),
        "other": mx("other_sessions", ["active_days"]),
        "rest": mx("rest_days")
    }

def league_text(state: dict, ym: str):
    league = state.get("leagues", {}).get(ym)
    if not league: return f"Sem liga registrada para {ym}."
    totals = league["totals"]
    def name(p): 
        u = (state.get("users") or {}).get(p) or {}
        return u.get("name") or p
    def rank_line(key, label, unit=""):
        items = sorted([(name(p), t[key]) for p,t in totals.items()], key=lambda x: x[1], reverse=True)
        fmt = lambda n,v: f"{n} {v:g}{(' '+unit) if unit else ''}"
        return f"{label}: " + " • ".join(fmt(n,v) for n,v in items)
    lines = [
        rank_line("active_days","Dias ativos","dias"),
        rank_line("run_km","Corrida","km"),
        rank_line("strength_sessions","Força","sessões"),
        rank_line("swim_m","Natação","m"),
        rank_line("other_sessions","Outros","sessões"),
        rank_line("rest_days","Descanso","dias"),
        f"Vencedor do mês: {name(league['winners']['overall'])}"
    ]
    return "*🏆 Liga "+ym+"*\n- " + "\n- ".join(lines)
