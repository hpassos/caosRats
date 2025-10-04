import os, re, json, asyncio
from datetime import datetime, timedelta, timezone, date
from dateutil.tz import gettz
from playwright.async_api import async_playwright
from jsonbin import get_state, put_state
from parser import parse_text
from league import compute_month_totals, pick_winners, month_bounds, league_text

GROUP_NAME = os.environ["WHATSAPP_GROUP_NAME"]
TZ = gettz("America/Sao_Paulo")

def today_brt():
    return datetime.now(tz=TZ).date()

def ym(d: date):
    return f"{d.year:04d}-{d.month:02d}"

async def open_group(page):
    # Abre o campo de busca e entra no grupo
    await page.click('[data-testid="chat-list-search"]', timeout=20000)
    await page.fill('[data-testid="chat-list-search"]', GROUP_NAME)
    # entra no resultado
    await page.wait_for_selector(f'text="{GROUP_NAME}"', timeout=15000)
    await page.click(f'text="{GROUP_NAME}"')

async def collect_day(page, day: date):
    # Garante que carregou a conversa
    await page.wait_for_selector('[data-testid="conversation-panel-messages"]', timeout=20000)

    # Rolagem para garantir que mensagens do dia atual estão na tela
    # Dica: WhatsApp Web marca cada mensagem com data no atributo data-pre-plain-text
    day_pat = day.strftime("%d/%m/%Y")  # [HH:MM, DD/MM/YYYY]
    items = await page.locator('div[role="row"] div[data-pre-plain-text]').all()

    # Se a conversa é longa, role para cima algumas vezes para garantir
    for _ in range(8):
        # tenta achar rapidamente alguma mensagem do dia
        for el in items:
            s = await el.get_attribute("data-pre-plain-text")
            if s and day_pat in s:
                break
        else:
            await page.mouse.wheel(0, -2000)
            await page.wait_for_timeout(800)
            items = await page.locator('div[role="row"] div[data-pre-plain-text]').all()
            continue
        break

    result = []
    for el in items:
        hdr = await el.get_attribute("data-pre-plain-text") or ""
        body = await el.inner_text()
        # hdr ex: "[18:23, 04/10/2025] Nome: "
        m = re.search(r"\[(\d{1,2}:\d{2}),\s*(\d{2}/\d{2}/\d{4})\]\s*(.*?):\s*$", hdr)
        if not m: 
            # mensagens do próprio usuário às vezes não trazem nome
            m = re.search(r"\[(\d{1,2}:\d{2}),\s*(\d{2}/\d{2}/\d{4})\]", hdr)
        if not m: 
            continue
        hhmm, dstr = m.group(1), m.group(2)
        if dstr != day.strftime("%d/%m/%Y"):
            continue
        # Para telefone/identificador, usamos o nome exibido enquanto fallback
        name = (m.group(3).strip() if len(m.groups()) >= 3 else "me").strip()
        result.append({"at": f"{dstr} {hhmm}", "sender": name, "text": body})
    return result

def normalize_sender(state: dict, sender: str) -> str:
    # Mapeie nomes para um "id" consistente. Simples: use o próprio nome como chave.
    # Você pode fazer um comando '!nome' depois para fixar nomes bonitos por telefone.
    users = state.setdefault("users", {})
    if sender not in users:
        users[sender] = {"name": sender}
    return sender

def record_text_messages(state: dict, day: date, msgs: list):
    acts = state.setdefault("activities", {})
    arr = acts.setdefault(day.isoformat(), [])
    seen_pairs = {(a.get("phone"), a.get("msgId")) for a in arr if a.get("msgId")}
    for i, m in enumerate(msgs):
        parsed = parse_text(m["text"])
        if not parsed:
            continue
        phone = normalize_sender(state, m["sender"])
        msg_id = f"{day.isoformat()}#{i}"
        if (phone, msg_id) in seen_pairs: 
            continue
        arr.append({
            "phone": phone,
            "type": parsed["type"],
            "metrics": parsed["metrics"],
            "msgId": msg_id
        })

def close_and_post_text(text: str) -> str:
    # Formata mensagem amigável para WhatsApp
    return text

async def post_to_group(page, text: str):
    try:
        box = page.locator('div[contenteditable="true"][role="textbox"]').last
        await box.click()
        await box.fill(text)
        await box.press("Enter")
    except Exception:
        # se falhar, apenas ignore. Postar é "nice to have"
        pass

async def run(target_date: date, post_summary: bool):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(storage_state="whatsapp_state.json")
        page = await ctx.new_page()
        await page.goto("https://web.whatsapp.com/")
        await page.wait_for_selector('[data-testid="chat-list"]', timeout=120_000)

        await open_group(page)
        msgs = await collect_day(page, target_date)

        state = get_state()
        record_text_messages(state, target_date, msgs)

        # atualiza liga do mês
        ym_key = ym(target_date.replace(day=1))
        totals = compute_month_totals(state, target_date.replace(day=1))
        winners = pick_winners(totals)
        leagues = state.setdefault("leagues", {})
        leagues[ym_key] = {"totals": totals, "winners": winners, "generated_at": datetime.utcnow().isoformat()}

        state = put_state(state)

        # resumo diário
        summary = build_daily_summary(state, target_date)
        if post_summary:
            await post_to_group(page, summary)

        await browser.close()
        return summary

def build_daily_summary(state: dict, day: date) -> str:
    arr = state.get("activities", {}).get(day.isoformat(), [])
    if not arr:
        return f"Resumo {day.isoformat()}: ninguém registrou treino."
    by = {}
    for a in arr:
        by.setdefault(a["phone"], []).append(a)
    def fmt(user, acts):
        parts = []
        for a in acts:
            t = a["type"]; m = a.get("metrics",{})
            if t == "run":
                inside = ", ".join([f'{m["km"]} km' if "km" in m else None,
                                    f'{m["min"]} min' if "min" in m else None,
                                    f'{m["pace"]}/km' if "pace" in m else None])
                parts.append("corrida (" + ", ".join([x for x in inside.split(", ") if x]) + ")")
            elif t == "strength":
                parts.append("força" + (f' ({m["min"]} min)' if "min" in m else ""))
            elif t == "swim":
                inside = ", ".join([f'{m["m"]} m' if "m" in m else None,
                                    f'{m["min"]} min' if "min" in m else None])
                parts.append("natação (" + ", ".join([x for x in inside.split(", ") if x]) + ")")
            else:
                parts.append("outros" + (f' ({m["min"]} min)' if "min" in m else ""))
        name = state.get("users", {}).get(user, {}).get("name", user)
        return f"{name}: " + " + ".join(parts)
    lines = " • ".join(fmt(u,v) for u,v in by.items())
    return f"*Resumo {day.isoformat()}*\n- {lines}"
    
if __name__ == "__main__":
    # Executa para hoje por padrão
    asyncio.run(run(today_brt(), post_summary=True))
