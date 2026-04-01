import argparse
import os
from datetime import datetime, timedelta, timezone

import psycopg2

from datos_simulados import ENTITIES

ENTITY_IDS = [e[0] for e in ENTITIES]


def parse_iso_utc(s):
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def as_utc(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def resolve_auto_gap(conn, end, recent_window_h, min_gap_h):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT MAX(time) FROM ltss WHERE entity_id = ANY(%s)",
            (ENTITY_IDS,),
        )
        gmax = as_utc(cur.fetchone()[0])
    if gmax is None:
        return None, None

    secs = int(recent_window_h * 3600)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MAX(l.time) FROM ltss l
            WHERE l.entity_id = ANY(%s)
              AND l.time < %s::timestamptz - (%s * interval '1 second')
            """,
            (ENTITY_IDS, gmax, secs),
        )
        subrow = cur.fetchone()[0]
    hist_end = as_utc(subrow) if subrow else None
    if hist_end is None:
        return None, None

    delta = gmax - hist_end
    if delta < timedelta(hours=min_gap_h):
        return None, None

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MIN(l.time) FROM ltss l
            WHERE l.entity_id = ANY(%s) AND l.time > %s
            """,
            (ENTITY_IDS, hist_end),
        )
        rmin = cur.fetchone()[0]
    recent_start = as_utc(rmin) if rmin else as_utc(end)

    return hist_end, recent_start


def main():
    p = argparse.ArgumentParser(
        description="Fill (hist_end, recent_start) by copying ltss from N calendar years earlier, shifted +N years in SQL."
    )
    p.add_argument("--host", default=os.environ.get("PGHOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PGPORT", "5432")))
    p.add_argument("--dbname", default=os.environ.get("PGDATABASE", "postgres"))
    p.add_argument("--user", default=os.environ.get("PGUSER", "postgres"))
    p.add_argument("--password", default=os.environ.get("PGPASSWORD", "Qwe1234."))
    p.add_argument(
        "--hist-end",
        default=None,
        help="ISO UTC: end of historical block; copied target times lie strictly after this.",
    )
    p.add_argument(
        "--recent-start",
        default=None,
        help="ISO UTC: start of recent block; copied target times lie strictly before this.",
    )
    p.add_argument(
        "--auto-gap",
        action="store_true",
        help="Infer hist-end and recent-start (dump vs recent cluster).",
    )
    p.add_argument("--recent-window-hours", type=float, default=24.0)
    p.add_argument("--min-gap-hours", type=float, default=72.0)
    p.add_argument("--years-ago", type=int, default=1)
    p.add_argument(
        "--delete-in-gap",
        action="store_true",
        help="Delete rows with time in (hist_end, recent_start) for known entities before insert.",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.years_ago < 1:
        raise SystemExit("--years-ago must be >= 1")

    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
    )
    conn.autocommit = True

    try:
        end = datetime.now(timezone.utc)
        if args.auto_gap:
            hist_end, recent_start = resolve_auto_gap(
                conn, end, args.recent_window_hours, args.min_gap_hours
            )
            if hist_end is None or recent_start is None:
                raise SystemExit(
                    "auto-gap: no qualifying gap (try --hist-end / --recent-start or lower --min-gap-hours)"
                )
            print(f"auto-gap hist_end={hist_end} recent_start={recent_start}")
        else:
            if not args.hist_end or not args.recent_start:
                raise SystemExit("Need --hist-end and --recent-start, or --auto-gap")
            hist_end = parse_iso_utc(args.hist_end)
            recent_start = parse_iso_utc(args.recent_start)

        if recent_start <= hist_end:
            raise SystemExit("recent-start must be after hist-end")

        y = args.years_ago
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM ltss l
                WHERE l.entity_id = ANY(%s)
                  AND l.time > (%s::timestamptz - make_interval(years => %s))
                  AND l.time < (%s::timestamptz - make_interval(years => %s))
                """,
                (ENTITY_IDS, hist_end, y, recent_start, y),
            )
            n_src = cur.fetchone()[0]

        print(
            f"source: rows between (hist_end - {y}y) and (recent_start - {y}y), count={n_src}"
        )

        if n_src == 0:
            print("No source rows; nothing to insert.")
            return

        if args.dry_run:
            print("Dry run: no changes.")
            return

        if args.delete_in_gap:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM ltss l
                    WHERE l.entity_id = ANY(%s)
                      AND l.time > %s AND l.time < %s
                    """,
                    (ENTITY_IDS, hist_end, recent_start),
                )
                print(f"Deleted {cur.rowcount} rows in gap.")

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ltss ("time", entity_id, state, attributes)
                SELECT
                    l.time + make_interval(years => %s),
                    l.entity_id,
                    l.state,
                    l.attributes
                FROM ltss l
                WHERE l.entity_id = ANY(%s)
                  AND l.time > (%s::timestamptz - make_interval(years => %s))
                  AND l.time < (%s::timestamptz - make_interval(years => %s))
                """,
                (y, ENTITY_IDS, hist_end, y, recent_start, y),
            )
            print(f"Inserted {cur.rowcount} rows.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
