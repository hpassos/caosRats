import re

def parse_text(text: str):
    t = (text or "").lower()
    type_ = (
        "run" if re.search(r"\bcorrida\b|run|🏃", t) else
        "bike" if re.search(r"bike|cicl|🚴", t) else
        "swim" if re.search(r"natação|natacao|swim|🏊", t) else
        "strength" if re.search(r"força|forca|muscul|🏋", t) else
        "other" if re.search(r"muay|boxe|luta|yoga|pilates", t) else
        None
    )

    def num(pat):
        m = re.search(pat, t)
        if not m: return None
        return float(m.group(1).replace(",", "."))

    km = num(r"(\d+(?:[.,]\d+)?)\s?(?:km|k)\b")
    m_swim = num(r"(\d{3,5})\s?m\b")
    mins = num(r"(\d+)\s?min\b")
    pace_m = re.search(r"\b(\d{1,2}:\d{2})\s*\/?\s*km\b", t)
    pace = pace_m.group(1) if pace_m else None

    if not any([type_, km, m_swim, mins, pace]):
        return None

    if not type_:
        type_ = "run" if km else ("swim" if m_swim else "other")

    metrics = {}
    if km is not None: metrics["km"] = km
    if m_swim is not None: metrics["m"] = m_swim
    if mins is not None: metrics["min"] = mins
    if pace: metrics["pace"] = pace
    return {"type": type_, "metrics": metrics}
