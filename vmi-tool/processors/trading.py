import csv
import io
from datetime import datetime, date

# Types to include and their VMI codes
INCLUDE = {
    "CASH TOP-UP": "II",
    "CASH WITHDRAWAL": "PP",
    "DIVIDEND": "IV",
}

# Everything else is silently skipped (BUY/SELL, DIVIDEND TAX, fees, splits, etc.)


def _parse_amount(amount_str: str) -> tuple[float, str]:
    """'USD -10.50' -> (10.50, 'USD'), 'EUR 9.00' -> (9.00, 'EUR')"""
    parts = amount_str.strip().split(" ", 1)
    if len(parts) == 2:
        return abs(float(parts[1])), parts[0]
    raise ValueError(f"Neatpažintas sumos formatas: {amount_str!r}")


def _parse_date(date_str: str) -> date:
    return datetime.fromisoformat(date_str.strip().replace("Z", "+00:00")).date()


def process(csv_content: str, year: int) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_content))

    required = {"Date", "Type", "Total Amount", "Currency", "FX Rate"}
    if reader.fieldnames and not required.issubset(set(reader.fieldnames)):
        raise ValueError(
            "CSV neatitinka Revolut Trading formato. "
            f"Tikėtini stulpeliai: {', '.join(sorted(required))}"
        )

    rows = []
    for row in reader:
        tx_type = row.get("Type", "").strip()
        vmi_code = INCLUDE.get(tx_type)
        if vmi_code is None:
            continue

        date_str = row.get("Date", "").strip()
        amount_str = row.get("Total Amount", "").strip()
        fx_str = row.get("FX Rate", "1").strip() or "1"

        if not date_str or not amount_str:
            continue

        try:
            tx_date = _parse_date(date_str)
        except Exception:
            continue

        if tx_date.year != year:
            continue

        try:
            amount, currency = _parse_amount(amount_str)
        except Exception:
            continue

        if currency != "EUR":
            try:
                fx = float(fx_str)
                amount = amount / fx
            except (ValueError, ZeroDivisionError):
                continue

        rows.append({"rusis": vmi_code, "data": tx_date, "suma": amount, "valstybe": "LT"})

    rows.sort(key=lambda r: (r["data"], r["rusis"]))
    return rows
