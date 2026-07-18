#!/usr/bin/env python3
"""
AI Agency Project Profitability Analyzer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A zero-dependency Python CLI tool for agencies to analyze project margins,
track budget burn, and identify client profitability trends.

Usage:
    python3 profitability_analyzer.py --help
    python3 profitability_analyzer.py --add-project "Project X" --client "Client A" --budget 15000 --hours-est 100
    python3 profitability_analyzer.py --add-entry --project-id 1 --hours 12 --cost-rate 75 --notes "Sprint planning"
    python3 profitability_analyzer.py --report
    python3 profitability_analyzer.py --report --format json
    python3 profitability_analyzer.py --dashboard

Pricing: $14 Standalone | $37 Bundle | $97 Agency License
"""

import json
import csv
import os
import sys
import datetime
import textwrap
from pathlib import Path

# ── Constants ────────────────────────────────────────────────────────────
APP_NAME = "Agency Project Profitability Analyzer"
VERSION = "1.0.0"
DATA_DIR = Path.home() / ".agency-profitability-analyzer"
PROJECTS_FILE = DATA_DIR / "projects.json"
ENTRIES_FILE = DATA_DIR / "entries.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
EXPORT_DIR = Path.cwd() / "profitability_exports"

DEFAULT_SETTINGS = {
    "hourly_bill_rate": 150,
    "internal_cost_rate": 50,
    "overhead_pct": 15,
    "target_margin_pct": 40,
    "currency_symbol": "$",
    "dashboard_theme": "dark"
}

# ── Data Helpers ─────────────────────────────────────────────────────────
def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

def load_json(path, default):
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default
    return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_projects():
    return load_json(PROJECTS_FILE, [])

def save_projects(projects):
    save_json(PROJECTS_FILE, projects)

def load_entries():
    return load_json(ENTRIES_FILE, [])

def save_entries(entries):
    save_json(ENTRIES_FILE, entries)

def load_settings():
    s = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
    merged = DEFAULT_SETTINGS.copy()
    merged.update(s)
    return merged

def save_settings(settings):
    save_json(SETTINGS_FILE, settings)

def next_id(items):
    return max((i.get("id", 0) for i in items), default=0) + 1

# ── Project CRUD ─────────────────────────────────────────────────────────
def add_project(name, client, budget, hours_est, rate=None, start_date=None, status="active"):
    projects = load_projects()
    pid = next_id(projects)
    project = {
        "id": pid,
        "name": name,
        "client": client,
        "budget": float(budget),
        "hours_estimated": float(hours_est),
        "bill_rate": rate or load_settings()["hourly_bill_rate"],
        "start_date": start_date or datetime.date.today().isoformat(),
        "status": status,
        "created_at": datetime.datetime.now().isoformat()
    }
    projects.append(project)
    save_projects(projects)
    print(f"✅ Project #{pid} '{name}' added (Client: {client}, Budget: {budget})")
    return pid

def list_projects(args):
    projects = load_projects()
    if not projects:
        print("📂 No projects found. Use --add-project to create one.")
        return
    print(f"\n{'ID':<4} {'Project':<30} {'Client':<25} {'Budget':<10} {'Hours':<8} {'Margin%':<8} {'Status':<10}")
    print("-" * 100)
    for p in projects:
        margin = calc_project_margin(p["id"])
        m_str = f"{margin:.1f}%" if margin is not None else "N/A"
        budget_str = f"${p['budget']:,.0f}"
        print(f"{p['id']:<4} {p['name'][:28]:<30} {p['client'][:23]:<25} "
              f"{budget_str:<10} {p['hours_estimated']:<8.0f} {m_str:<8} {(p.get('status') or 'active'):<10}")

def calc_project_margin(project_id):
    entries = [e for e in load_entries() if e.get("project_id") == project_id]
    projects = load_projects()
    project = next((p for p in projects if p["id"] == project_id), None)
    if not project:
        return None
    total_cost = sum(e.get("hours", 0) * e.get("cost_rate", 0) for e in entries)
    settings = load_settings()
    overhead = total_cost * (settings["overhead_pct"] / 100)
    total_expense = total_cost + overhead
    if total_expense == 0:
        return 0.0
    return ((project["budget"] - total_expense) / project["budget"]) * 100

# ── Time Entry CRUD ──────────────────────────────────────────────────────
def add_entry(project_id, hours, cost_rate=None, bill_rate=None, notes="", date=None):
    entries = load_entries()
    eid = next_id(entries)
    entry = {
        "id": eid,
        "project_id": project_id,
        "hours": float(hours),
        "cost_rate": cost_rate or load_settings()["internal_cost_rate"],
        "bill_rate": bill_rate or load_settings()["hourly_bill_rate"],
        "notes": notes,
        "date": date or datetime.date.today().isoformat(),
        "created_at": datetime.datetime.now().isoformat()
    }
    entries.append(entry)
    save_entries(entries)
    print(f"✅ Entry #{eid} added: {hours}h to Project #{project_id} (Cost: ${cost_rate or load_settings()['internal_cost_rate']}/h)")
    return eid

# ── Reporting ────────────────────────────────────────────────────────────
def generate_report(format="console"):
    projects = load_projects()
    entries = load_entries()
    settings = load_settings()

    if not projects:
        print("No projects to analyze.")
        return

    report_data = []
    for p in projects:
        pe = [e for e in entries if e.get("project_id") == p["id"]]
        total_hours = sum(e.get("hours", 0) for e in pe)
        total_cost = sum(e.get("hours", 0) * e.get("cost_rate", 0) for e in pe)
        total_billed = sum(e.get("hours", 0) * e.get("bill_rate", 0) for e in pe)
        overhead = total_cost * (settings["overhead_pct"] / 100)
        total_expense = total_cost + overhead
        remaining_budget = p["budget"] - total_billed
        hours_remaining = p["hours_estimated"] - total_hours
        budget_util_pct = (total_billed / p["budget"] * 100) if p["budget"] > 0 else 0
        hours_util_pct = (total_hours / p["hours_estimated"] * 100) if p["hours_estimated"] > 0 else 0

        effective_rate = total_billed / total_hours if total_hours > 0 else 0
        profit = total_billed - total_expense
        margin_pct = (profit / total_billed * 100) if total_billed > 0 else 0
        margin_vs_target = margin_pct - settings["target_margin_pct"]

        report_data.append({
            "project": p["name"],
            "client": p["client"],
            "budget": p["budget"],
            "hours_estimated": p["hours_estimated"],
            "total_hours_logged": round(total_hours, 1),
            "total_cost": round(total_cost, 2),
            "total_billed": round(total_billed, 2),
            "overhead": round(overhead, 2),
            "total_expense": round(total_expense, 2),
            "remaining_budget": round(remaining_budget, 2),
            "hours_remaining": round(hours_remaining, 1),
            "budget_util_pct": round(budget_util_pct, 1),
            "hours_util_pct": round(hours_util_pct, 1),
            "effective_rate": round(effective_rate, 2),
            "profit": round(profit, 2),
            "margin_pct": round(margin_pct, 1),
            "margin_vs_target": round(margin_vs_target, 1),
            "status": p.get("status", "active"),
            "entry_count": len(pe)
        })

    if format == "json":
        print(json.dumps(report_data, indent=2))
        return report_data

    curr = settings["currency_symbol"]
    print(f"\n{'='*80}")
    print(f"  📊 AGENCY PROJECT PROFITABILITY REPORT")
    print(f"  Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*80}")
    print(f"  Settings: {curr}{settings['hourly_bill_rate']}/h bill rate | {settings['overhead_pct']}% overhead | {settings['target_margin_pct']}% target margin")
    print(f"{'='*80}\n")

    total_budget = 0
    total_billed = 0
    total_cost = 0
    total_hours = 0

    for rd in report_data:
        print(f"  ┌─ {rd['project']} ({rd['client']}) [Status: {rd['status']}]")
        print(f"  │   Budget:       {curr}{rd['budget']:>10,.2f}  │  Used: {rd['budget_util_pct']:>5.1f}%  │  Remaining: {curr}{rd['remaining_budget']:>10,.2f}")
        print(f"  │   Hours Est.:   {rd['hours_estimated']:>10.0f}  │  Logged: {rd['total_hours_logged']:>7.1f}h  │  Remaining: {rd['hours_remaining']:>7.1f}h")
        print(f"  │   Billed:       {curr}{rd['total_billed']:>10,.2f}  │  Cost: {curr}{rd['total_cost']:>10,.2f}  │  Overhead: {curr}{rd['overhead']:>10,.2f}")
        print(f"  │   Effective Rate: {curr}{rd['effective_rate']:>8,.2f}/h  │  Profit: {curr}{rd['profit']:>10,.2f}")
        margin_color = "🟢" if rd['margin_pct'] >= settings['target_margin_pct'] else ("🟡" if rd['margin_pct'] >= settings['target_margin_pct'] * 0.75 else "🔴")
        print(f"  │   {margin_color} Margin: {rd['margin_pct']:>6.1f}%  │  vs Target: {rd['margin_vs_target']:>+6.1f}pp  │  Entries: {rd['entry_count']}")
        print(f"  └{'─'*60}")
        total_budget += rd['budget']
        total_billed += rd['total_billed']
        total_cost += rd['total_cost']
        total_hours += rd['total_hours_logged']

    total_overhead = total_cost * (settings["overhead_pct"] / 100)
    total_expense = total_cost + total_overhead
    total_profit = total_billed - total_expense
    avg_margin = (total_profit / total_billed * 100) if total_billed > 0 else 0

    print(f"\n  {'═'*60}")
    print(f"  📈 PORTFOLIO SUMMARY")
    print(f"  {'═'*60}")
    print(f"  Projects: {len(report_data)}  │  Total Budget: {curr}{total_budget:>10,.2f}")
    print(f"  Total Billed: {curr}{total_billed:>10,.2f}  │  Total Cost: {curr}{total_cost:>10,.2f}")
    print(f"  Total Overhead: {curr}{total_overhead:>10,.2f}  │  Total Expense: {curr}{total_expense:>10,.2f}")
    print(f"  Total Profit: {curr}{total_profit:>10,.2f}  │  Avg Margin: {avg_margin:>6.1f}%")
    print(f"  Total Hours: {total_hours:>8.1f}  │  Portfolio Health: {'🟢' if avg_margin >= settings['target_margin_pct'] else '🟡' if avg_margin >= settings['target_margin_pct']*0.75 else '🔴'}")
    print(f"  {'═'*60}\n")
    return report_data

# ── HTML Dashboard ──────────────────────────────────────────────────────
def generate_dashboard():
    ensure_data_dir()
    report = generate_report("json")
    if not report:
        return
    settings = load_settings()
    curr = settings["currency_symbol"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agency Project Profitability Dashboard</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Inter',system-ui,-apple-system,sans-serif; background:#05070a; color:#f0f6fc; min-height:100vh; }}
body::before {{ content:''; position:fixed; inset:0;
  background-image:linear-gradient(rgba(245,158,11,0.03) 1px,transparent 1px),
  linear-gradient(90deg,rgba(245,158,11,0.03) 1px,transparent 1px);
  background-size:60px 60px; pointer-events:none; z-index:0; }}
.container {{ max-width:1200px; margin:0 auto; padding:2rem; position:relative; z-index:1; }}
header {{ text-align:center; padding:3rem 0 2rem; }}
h1 {{ font-size:2.5rem; font-weight:800; background:linear-gradient(135deg,#f59e0b,#d97706,#b45309);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.badge {{ display:inline-block; background:rgba(245,158,11,0.12); color:#f59e0b; border:1px solid rgba(245,158,11,0.25);
  padding:0.3rem 1rem; border-radius:100px; font-size:0.8rem; margin-bottom:1rem; }}
.summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:1rem; margin:2rem 0; }}
.card {{ background:#0d1117; border:1px solid #21262d; border-radius:12px; padding:1.5rem; text-align:center; }}
.card .label {{ color:#8b949e; font-size:0.85rem; text-transform:uppercase; letter-spacing:0.05em; }}
.card .value {{ font-size:1.8rem; font-weight:700; margin-top:0.3rem; }}
.card .value.green {{ color:#22c55e; }} .card .value.amber {{ color:#f59e0b; }} .card .value.red {{ color:#ef4444; }}
.card .sub {{ color:#8b949e; font-size:0.8rem; margin-top:0.2rem; }}
table {{ width:100%; border-collapse:collapse; margin-top:2rem; }}
th {{ background:#161b22; color:#8b949e; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.05em;
  padding:0.8rem 1rem; text-align:left; border-bottom:1px solid #21262d; }}
td {{ padding:0.8rem 1rem; border-bottom:1px solid #161b22; }}
tr:hover {{ background:rgba(245,158,11,0.04); }}
.bar {{ height:6px; border-radius:3px; background:#21262d; margin-top:4px; }}
.bar-fill {{ height:6px; border-radius:3px; background:linear-gradient(90deg,#f59e0b,#d97706); }}
.tag {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:0.75rem; }}
.tag-active {{ background:rgba(34,197,94,0.15); color:#22c55e; border:1px solid rgba(34,197,94,0.3); }}
.tag-atrisk {{ background:rgba(245,158,11,0.15); color:#f59e0b; border:1px solid rgba(245,158,11,0.3); }}
.tag-danger {{ background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid rgba(239,68,68,0.3); }}
.footer {{ text-align:center; color:#8b949e; font-size:0.8rem; margin-top:3rem; padding-top:1.5rem;
  border-top:1px solid #21262d; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="badge">AI Agency Tool • v{VERSION}</div>
    <h1>📊 Project Profitability Dashboard</h1>
    <p style="color:#8b949e;margin-top:0.5rem;">Generated {datetime.datetime.now().strftime('%B %d, %Y at %H:%M')}</p>
  </header>
"""
    total_budget = sum(r["budget"] for r in report)
    total_billed = sum(r["total_billed"] for r in report)
    total_cost = sum(r["total_cost"] for r in report)
    total_hours = sum(r["total_hours_logged"] for r in report)
    total_profit = sum(r["profit"] for r in report)
    avg_margin = (total_profit / total_billed * 100) if total_billed > 0 else 0
    risk_count = sum(1 for r in report if r["margin_pct"] < settings["target_margin_pct"] * 0.75)

    html += f"""
  <div class="summary">
    <div class="card"><div class="label">Total Budget</div><div class="value amber">{curr}{total_budget:,.0f}</div></div>
    <div class="card"><div class="label">Total Billed</div><div class="value amber">{curr}{total_billed:,.0f}</div></div>
    <div class="card"><div class="label">Total Cost</div><div class="value">{curr}{total_cost:,.0f}</div></div>
    <div class="card"><div class="label">Profit</div><div class="value green">{curr}{total_profit:,.0f}</div></div>
    <div class="card"><div class="label">Avg Margin</div><div class="value {'green' if avg_margin>=settings['target_margin_pct'] else 'red'}">{avg_margin:.1f}%</div>
      <div class="sub">Target: {settings['target_margin_pct']}%</div></div>
    <div class="card"><div class="label">Total Hours</div><div class="value">{total_hours:,.0f}</div><div class="sub">{len(report)} projects</div></div>
  </div>
  <h2 style="margin-top:2rem;font-size:1.3rem;">📋 Project Detail</h2>
  <table>
    <tr><th>Project</th><th>Client</th><th>Budget</th><th>Billed</th><th>Hours</th><th>Margin</th><th>Health</th></tr>
"""
    for r in report:
        margin = r["margin_pct"]
        health = "tag-active" if margin >= settings["target_margin_pct"] else ("tag-atrisk" if margin >= settings["target_margin_pct"] * 0.75 else "tag-danger")
        health_label = "✅ Healthy" if margin >= settings["target_margin_pct"] else ("⚠️ At Risk" if margin >= settings["target_margin_pct"] * 0.75 else "🔴 Critical")
        bar_pct = min(r["budget_util_pct"], 100)
        html += f"""
    <tr>
      <td><strong>{r['project']}</strong></td>
      <td style="color:#8b949e;">{r['client']}</td>
      <td>{curr}{r['budget']:,.0f}</td>
      <td>{curr}{r['total_billed']:,.0f}</td>
      <td>{r['total_hours_logged']:.1f}</td>
      <td style="color:{'#22c55e' if margin>=settings['target_margin_pct'] else '#f59e0b' if margin>=settings['target_margin_pct']*0.75 else '#ef4444'}">{margin:.1f}%</td>
      <td><span class="tag {health}">{health_label}</span></td>
    </tr>
    <tr style="background:transparent;"><td colspan="7" style="padding:0 1rem 0.5rem;">
      <div class="bar"><div class="bar-fill" style="width:{bar_pct}%"></div></div>
      <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:#8b949e;margin-top:2px;">
        <span>{bar_pct:.0f}% budget used</span>
        <span>{curr}{r['remaining_budget']:,.0f} remaining</span>
      </div>
    </td></tr>"""

    html += f"""
  </table>
  <div class="footer">
    <p><strong>{APP_NAME}</strong> v{VERSION} — Standalone {curr}14 | Bundle {curr}37 | Agency License {curr}97</p>
    <p style="margin-top:0.5rem;">⚠️ Projects at critical margin: {risk_count} of {len(report)}</p>
  </div>
</div>
</body>
</html>"""

    out_path = EXPORT_DIR / "profitability_dashboard.html"
    with open(out_path, "w") as f:
        f.write(html)
    print(f"✅ Dashboard exported: {out_path}")
    return out_path

# ── CSV Export ───────────────────────────────────────────────────────────
def export_csv():
    ensure_data_dir()
    report = generate_report("json")
    if not report:
        return
    out_path = EXPORT_DIR / "profitability_report.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=report[0].keys())
        writer.writeheader()
        writer.writerows(report)
    print(f"✅ CSV exported: {out_path}")

# ── CLI ──────────────────────────────────────────────────────────────────
def show_help():
    print(f"""
{APP_NAME} v{VERSION}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

USAGE:
  python3 profitability_analyzer.py [COMMAND] [OPTIONS]

COMMANDS:
  --add-project <name> --client <name> --budget <amt> --hours-est <n>
      Add a new project. Optional: --rate <n> --start-date YYYY-MM-DD
  
  --add-entry --project-id <id> --hours <n> --cost-rate <n>
      Log time entry. Optional: --bill-rate <n> --notes "..." --date YYYY-MM-DD
  
  --list-projects             List all projects with margin overview
  --report [--format console|json]
      Generate profitability report
  --dashboard                 Export interactive HTML dashboard
  --export-csv                Export report as CSV
  --settings                  Show current settings
  --set <key>=<value>         Update a setting

SETTINGS:
  hourly_bill_rate     Default client bill rate per hour ({DEFAULT_SETTINGS['hourly_bill_rate']})
  internal_cost_rate   Internal team cost per hour ({DEFAULT_SETTINGS['internal_cost_rate']})
  overhead_pct         Overhead as percentage of cost ({DEFAULT_SETTINGS['overhead_pct']}%)
  target_margin_pct    Target profit margin ({DEFAULT_SETTINGS['target_margin_pct']}%)
  currency_symbol      Currency symbol ({DEFAULT_SETTINGS['currency_symbol']})

EXAMPLES:
  python3 profitability_analyzer.py --add-project "Website Redesign" --client "Acme Corp" --budget 25000 --hours-est 200
  python3 profitability_analyzer.py --add-entry --project-id 1 --hours 8 --cost-rate 65 --notes "UI design sprint"
  python3 profitability_analyzer.py --report
  python3 profitability_analyzer.py --dashboard
  python3 profitability_analyzer.py --set target_margin_pct=35

PRICING: {chr(36)}14 Standalone | {chr(36)}37 Bundle | {chr(36)}97 Agency License
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

def main():
    ensure_data_dir()
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        show_help()
        return

    if args[0] == "--add-project":
        def get_arg(key):
            try:
                idx = args.index(key)
                return args[idx + 1]
            except (ValueError, IndexError):
                return None
        # First positional value after --add-project is the project name
        name = get_arg("--name") or get_arg("--project") or (args[1] if len(args) > 1 and not args[1].startswith("--") else None)
        client = get_arg("--client") or get_arg("--company")
        budget = get_arg("--budget")
        hours = get_arg("--hours-est") or get_arg("--hours")
        rate = get_arg("--rate")
        start = get_arg("--start-date")
        status = get_arg("--status")
        if not all([name, client, budget, hours]):
            print("❌ Required: --name or positional name, --client, --budget, --hours-est")
            sys.exit(1)
        add_project(name, client, float(budget), float(hours),
                    rate=float(rate) if rate else None,
                    start_date=start, status=status)
        return

    if args[0] == "--add-entry":
        def get_arg(key):
            try:
                idx = args.index(key)
                return args[idx + 1]
            except (ValueError, IndexError):
                return None
        pid = get_arg("--project-id")
        hours = get_arg("--hours")
        cost = get_arg("--cost-rate")
        bill = get_arg("--bill-rate")
        notes = get_arg("--notes")
        date = get_arg("--date")
        if not all([pid, hours]):
            print("❌ Required: --project-id, --hours")
            sys.exit(1)
        add_entry(int(pid), float(hours),
                  cost_rate=float(cost) if cost else None,
                  bill_rate=float(bill) if bill else None,
                  notes=notes or "",
                  date=date)
        return

    if args[0] == "--list-projects":
        list_projects(args)
        return

    if args[0] == "--report":
        fmt = "console"
        if "--format" in args:
            try:
                fmt = args[args.index("--format") + 1]
            except IndexError:
                pass
        generate_report(fmt)
        return

    if args[0] == "--dashboard":
        path = generate_dashboard()
        if path:
            print(f"\n📂 Open: file://{path.absolute()}")
        return

    if args[0] == "--export-csv":
        export_csv()
        return

    if args[0] == "--settings":
        s = load_settings()
        for k, v in s.items():
            print(f"  {k} = {v}")
        return

    if args[0] == "--set":
        if len(args) < 2:
            print("❌ Usage: --set key=value")
            sys.exit(1)
        try:
            key, val = args[1].split("=", 1)
        except ValueError:
            print("❌ Format: --set key=value")
            sys.exit(1)
        s = load_settings()
        if key not in DEFAULT_SETTINGS:
            print(f"❌ Unknown setting: {key}. Valid: {', '.join(DEFAULT_SETTINGS.keys())}")
            sys.exit(1)
        try:
            if isinstance(DEFAULT_SETTINGS[key], int):
                val = int(val)
            elif isinstance(DEFAULT_SETTINGS[key], float):
                val = float(val)
        except ValueError:
            print(f"❌ Invalid value for {key}: expected {type(DEFAULT_SETTINGS[key]).__name__}")
            sys.exit(1)
        s[key] = val
        save_settings(s)
        print(f"✅ Set {key} = {val}")
        return

    print(f"❌ Unknown command: {args[0]}")
    show_help()
    sys.exit(1)

if __name__ == "__main__":
    main()