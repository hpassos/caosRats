import os, asyncio
from datetime import datetime, timedelta, date
from dateutil.parser import isoparse
from dateutil.tz import gettz
from scrape_daily import run

# Executa varrendo do 'since' até ontem no fuso BRT
# Uso: python backfill.py 2025-09-01
def daterange(start: date, end: date):
    while start <= end:
        yield start
        start += timedelta(days=1)

if __name__ == "__main__":
    import sys
    tz = gettz("America/Sao_Paulo")
    since = isoparse(sys.argv[1]).date() if len(sys.argv) > 1 else (datetime.now(tz=tz).date() - timedelta(days=30))
    today = datetime.now(tz=tz).date()
    for d in daterange(since, today):
        asyncio.run(run(d, post_summary=False))
