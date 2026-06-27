"""
Scheduler giornaliero: ripristina 'available' le bici con restituzione scaduta.

Eseguire ogni giorno alle 07:00 tramite:

  Linux/macOS (cron):
      0 7 * * * /path/to/venv/bin/python3 /path/to/bikesharing/scheduler.py

  Windows (Task Scheduler):
      Trigger: Daily, 07:00
      Action:  C:\\path\\to\\venv\\Scripts\\python.exe C:\\path\\to\\bikesharing\\scheduler.py
      Start in: C:\\path\\to\\bikesharing

Lo script usa DB_PATH da .env (default: bikesharing.db nella working directory).
Exit code 0 in successo, 1 in caso di eccezione non gestita.
"""

import sys
from datetime import datetime, timezone

import db


def main() -> None:
    db.init_db()
    count = db.restore_overdue_bikes()
    print(
        f"[{datetime.now(timezone.utc).isoformat()}] restore_overdue_bikes: {count} bici ripristinate"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[{datetime.now(timezone.utc).isoformat()}] ERRORE: {exc}", file=sys.stderr)
        sys.exit(1)
