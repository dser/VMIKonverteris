import csv
import io
from datetime import datetime, date


def _parse_date(date_str: str) -> date:
    """'Apr 17, 2026, 3:12:25 AM' -> date"""
    return datetime.strptime(date_str.strip(), "%b %d, %Y, %I:%M:%S %p").date()


def process(csv_content: str, year: int) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_content))

    # Find the value column (named "Value, EUR" in the CSV)
    value_col = None
    if reader.fieldnames:
        value_col = next((c for c in reader.fieldnames if "Value" in c), None)

    if value_col is None:
        raise ValueError(
            "CSV neatitinka Revolut Flexible Cash Fund formato. "
            "Nerasta 'Value' reikšmių kolona."
        )

    all_rows: list[dict] = []
    for row in reader:
        date_str = row.get("Date", "").strip()
        desc = row.get("Description", "").strip()
        val_str = row.get(value_col, "").strip()

        if not date_str or not val_str:
            continue

        try:
            tx_date = _parse_date(date_str)
            value = float(val_str)
        except Exception:
            continue

        all_rows.append({"date": tx_date, "desc": desc, "value": value})

    # Identify reinvestment pairs: "Interest Reinvested" (negative) + matching BUY
    # within 5 days with the same absolute amount → skip both
    reinvested = [
        {"date": r["date"], "amount": abs(r["value"]), "matched": False, "id": id(r)}
        for r in all_rows
        if "Interest Reinvested" in r["desc"]
    ]

    skip_ids: set[int] = set()
    for r in all_rows:
        if "BUY" not in r["desc"]:
            continue
        buy_amount = abs(r["value"])
        for ri in reinvested:
            if ri["matched"]:
                continue
            if abs((r["date"] - ri["date"]).days) <= 5 and abs(ri["amount"] - buy_amount) < 0.01:
                ri["matched"] = True
                skip_ids.add(id(r))
                # also mark the reinvested row itself
                for orig in all_rows:
                    if "Interest Reinvested" in orig["desc"] and id(orig) == ri["id"]:
                        skip_ids.add(id(orig))
                break

    result: list[dict] = []
    for r in all_rows:
        if r["date"].year != year:
            continue
        if id(r) in skip_ids:
            continue

        desc = r["desc"]
        if "Interest PAID" in desc:
            result.append({"rusis": "IV", "data": r["date"], "suma": abs(r["value"]), "valstybe": "LT"})
        elif "BUY" in desc:
            # Unmatched BUY = real manual top-up
            result.append({"rusis": "II", "data": r["date"], "suma": abs(r["value"]), "valstybe": "LT"})
        # Service fees and Interest Reinvested: skip

    result.sort(key=lambda r: (r["data"], r["rusis"]))
    return result
