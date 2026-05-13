import datetime
import os

# Hourly rates per client
HOURLY_RATES = {
    "CEMEX":   125.0,
    "CFP":     125.0,
    "DEACERO":  82.0,
}

# Notion database IDs for each client's time log
TIME_LOG_DATABASES = {
    "CEMEX":   "078eca46-ef5f-4602-9c56-37887a43b670",
    "CFP":     "8494fb0a-b831-4063-84c5-346f96d4ca8c",
    "DEACERO": "0f697f8a-e3b9-4f48-8fd9-1c98d5fdf3b4",
}

AI_LEADS_CRM_ID = "b285e78b-ede5-4b0a-8798-126b86fa58e6"


def get_monthly_revenue() -> dict:
    token = os.environ.get("NOTION_API_TOKEN")
    if not token:
        print("[REVENUE] NOTION_API_TOKEN is not set — skipping revenue data.")
        return {}

    print(f"[REVENUE] NOTION_API_TOKEN is set (length: {len(token)})")

    try:
        from notion_client import Client
        notion = Client(auth=token)
    except ImportError:
        print("[REVENUE] notion-client package not installed.")
        return {}

    today = datetime.date.today()
    month_start = today.replace(day=1).isoformat()
    if today.month == 12:
        month_end = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(days=1)
    else:
        month_end = today.replace(month=today.month + 1, day=1) - datetime.timedelta(days=1)
    month_end = month_end.isoformat()
    month_name = today.strftime("%B %Y")

    print(f"[REVENUE] Querying for {month_name} ({month_start} to {month_end})")

    client_revenue = {}
    total_earned = 0.0
    access_errors = []

    for client_name, db_id in TIME_LOG_DATABASES.items():
        rate = HOURLY_RATES[client_name]
        print(f"[REVENUE] Querying {client_name} (db: {db_id})...")
        try:
            response = notion.databases.query(
                database_id=db_id,
                page_size=100,
                filter={
                    "and": [
                        {"property": "Date", "date": {"on_or_after": month_start}},
                        {"property": "Date", "date": {"on_or_before": month_end}},
                        {"property": "Billable", "checkbox": {"equals": True}},
                    ]
                },
            )
            total_hours = _sum_hours(response)
            print(f"[REVENUE]   {client_name}: {len(response.get('results', []))} entries, {total_hours:.1f} billable hours")

            while response.get("has_more"):
                response = notion.databases.query(
                    database_id=db_id, page_size=100,
                    filter={
                        "and": [
                            {"property": "Date", "date": {"on_or_after": month_start}},
                            {"property": "Date", "date": {"on_or_before": month_end}},
                            {"property": "Billable", "checkbox": {"equals": True}},
                        ]
                    },
                    start_cursor=response["next_cursor"],
                )
                total_hours += _sum_hours(response)

            revenue = round(total_hours * rate, 2)
            total_earned += revenue
            client_revenue[client_name] = {
                "hours": round(total_hours, 1),
                "rate": rate,
                "revenue": revenue,
            }
            print(f"[REVENUE]   {client_name}: {total_hours:.1f} hrs x ${rate} = ${revenue:.2f}")

        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            print(f"[REVENUE] ERROR querying {client_name}: {err_msg}")
            access_errors.append(f"{client_name} ({err_msg})")
            client_revenue[client_name] = {"hours": 0.0, "rate": rate, "revenue": 0.0}

    print(f"[REVENUE] Total earned this month: ${total_earned:.2f}")

    print("[REVENUE] Querying AI Leads CRM...")
    pipeline = _get_pipeline(notion)
    print(f"[REVENUE] Pipeline: ${pipeline.get('total_value', 0):.2f} across {pipeline.get('active_count', 0)} leads")

    result = {
        "month": month_name,
        "clients": client_revenue,
        "total_earned": round(total_earned, 2),
        "pipeline": pipeline,
    }
    if access_errors:
        result["access_errors"] = access_errors
    return result


def _sum_hours(response: dict) -> float:
    total = 0.0
    for page in response.get("results", []):
        h = page.get("properties", {}).get("Hours", {})
        if h.get("type") == "number" and h.get("number") is not None:
            total += h["number"]
    return total


def _get_pipeline(notion) -> dict:
    try:
        response = notion.databases.query(
            database_id=AI_LEADS_CRM_ID,
            page_size=100,
            filter={
                "and": [
                    {"property": "Stage", "select": {"does_not_equal": "Lost"}},
                    {"property": "Stage", "select": {"does_not_equal": "Completed"}},
                    {"property": "Stage", "select": {"does_not_equal": "Training completed"}},
                ]
            },
        )
        print(f"[REVENUE]   CRM returned {len(response.get('results', []))} active leads")

        total_value = 0.0
        active_count = 0
        hot_leads = []

        for page in response.get("results", []):
            props = page.get("properties", {})
            revenue_val = (props.get("Revenue") or {}).get("number") or 0
            total_value += revenue_val
            active_count += 1

            name = "".join(
                t.get("plain_text", "") for t in (props.get("Name") or {}).get("title", [])
            )
            stage = ((props.get("Stage") or {}).get("select") or {}).get("name", "")
            priority = ((props.get("Priority") or {}).get("select") or {}).get("name", "")
            next_action = "".join(
                t.get("plain_text", "") for t in (props.get("Next Action") or {}).get("rich_text", [])
            )
            next_action_date = (
                (props.get("Next Action Date") or {}).get("date") or {}
            ).get("start", "")
            company = "".join(
                t.get("plain_text", "") for t in (props.get("Company") or {}).get("rich_text", [])
            )

            if priority == "High":
                hot_leads.append({
                    "name": name,
                    "company": company,
                    "stage": stage,
                    "revenue": revenue_val,
                    "next_action": next_action,
                    "next_action_date": next_action_date,
                })

        hot_leads.sort(key=lambda x: x.get("next_action_date") or "9999")
        return {
            "total_value": round(total_value, 2),
            "active_count": active_count,
            "hot_leads": hot_leads[:5],
        }

    except Exception as e:
        print(f"[REVENUE] ERROR querying AI Leads CRM: {type(e).__name__}: {e}")
        return {"total_value": 0.0, "active_count": 0, "hot_leads": []}
