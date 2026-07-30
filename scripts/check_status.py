import sqlite3

conn = sqlite3.connect('automation.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== WORKFLOW RUNS - Status Summary ===")
cur.execute("SELECT execution_status, delivery_status, COUNT(*) as cnt FROM workflow_runs GROUP BY execution_status, delivery_status")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  execution_status={r['execution_status']} | delivery_status={r['delivery_status']} | count={r['cnt']}")
else:
    print("  No workflow runs found")

print()
print("=== PENDING WORKFLOW RUNS ===")
cur.execute("SELECT id, user_id, execution_status, delivery_status, created_at, updated_at FROM workflow_runs WHERE execution_status='pending' OR delivery_status='pending'")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(dict(r))
else:
    print("  No pending workflow runs")

print()
print("=== SCHEDULED WORKFLOWS ===")
cur.execute("SELECT id, name, last_status, is_active, schedule_value, next_run_at, total_runs FROM scheduled_workflows")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(dict(r))
else:
    print("  No scheduled workflows found")

print()
print("=== TABLE COUNTS ===")
for table in ['workflow_runs', 'scheduled_workflows', 'idempotency_records']:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"  {table}: {cur.fetchone()[0]} rows")

conn.close()
