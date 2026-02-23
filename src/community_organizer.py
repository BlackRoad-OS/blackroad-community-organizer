#!/usr/bin/env python3
"""BlackRoad Community Organizer - events, members, RSVPs."""

from __future__ import annotations
import argparse
import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

GREEN = "\033[0;32m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
BOLD = "\033[1m"
NC = "\033[0m"

DB_PATH = Path.home() / ".blackroad" / "community-organizer.db"


@dataclass
class Member:
    id: int
    name: str
    email: str
    role: str
    joined_at: str
    active: int


@dataclass
class Event:
    id: int
    title: str
    description: str
    location: str
    event_date: str
    capacity: int
    organizer_id: int
    created_at: str
    status: str


@dataclass
class RSVP:
    id: int
    event_id: int
    member_id: int
    response: str
    rsvp_at: str
    notes: str


class CommunityOrganizer:
    """Community event and member management system."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    role TEXT DEFAULT 'member',
                    joined_at TEXT NOT NULL,
                    active INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    location TEXT DEFAULT 'TBD',
                    event_date TEXT NOT NULL,
                    capacity INTEGER DEFAULT 50,
                    organizer_id INTEGER REFERENCES members(id),
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'upcoming'
                );
                CREATE TABLE IF NOT EXISTS rsvps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL REFERENCES events(id),
                    member_id INTEGER NOT NULL REFERENCES members(id),
                    response TEXT DEFAULT 'attending',
                    rsvp_at TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    UNIQUE(event_id, member_id)
                );
                CREATE INDEX IF NOT EXISTS idx_rsvps_event ON rsvps(event_id);
            """)

    def add_member(self, name: str, email: str, role: str = "member") -> Member:
        """Register a community member."""
        with sqlite3.connect(self.db_path) as conn:
            now = datetime.now().isoformat()
            cur = conn.execute(
                "INSERT INTO members (name,email,role,joined_at) VALUES (?,?,?,?)",
                (name, email, role, now),
            )
            return Member(cur.lastrowid, name, email, role, now, 1)

    def create_event(self, title: str, event_date: str, location: str = "TBD",
                     description: str = "", capacity: int = 50,
                     organizer_email: str = None) -> Event:
        """Create a community event."""
        with sqlite3.connect(self.db_path) as conn:
            organizer_id = None
            if organizer_email:
                row = conn.execute(
                    "SELECT id FROM members WHERE email=?", (organizer_email,)
                ).fetchone()
                if row:
                    organizer_id = row[0]
            now = datetime.now().isoformat()
            cur = conn.execute(
                "INSERT INTO events (title,description,location,event_date,capacity,organizer_id,created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (title, description, location, event_date, capacity, organizer_id, now),
            )
            return Event(cur.lastrowid, title, description, location,
                         event_date, capacity, organizer_id, now, "upcoming")

    def rsvp(self, event_id: int, member_email: str,
             response: str = "attending", notes: str = "") -> RSVP:
        """Record an RSVP for an event."""
        with sqlite3.connect(self.db_path) as conn:
            m = conn.execute("SELECT id FROM members WHERE email=?", (member_email,)).fetchone()
            if not m:
                raise ValueError(f"Member '{member_email}' not found")
            now = datetime.now().isoformat()
            cur = conn.execute(
                "INSERT OR REPLACE INTO rsvps (event_id,member_id,response,rsvp_at,notes)"
                " VALUES (?,?,?,?,?)",
                (event_id, m[0], response, now, notes),
            )
            return RSVP(cur.lastrowid, event_id, m[0], response, now, notes)

    def list_events(self, status: str = None) -> list:
        """List events optionally filtered by status."""
        with sqlite3.connect(self.db_path) as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM events WHERE status=? ORDER BY event_date", (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM events ORDER BY event_date"
                ).fetchall()
            return [Event(*r) for r in rows]

    def list_members(self) -> list:
        """Return active members."""
        with sqlite3.connect(self.db_path) as conn:
            return [Member(*r) for r in
                    conn.execute("SELECT * FROM members WHERE active=1").fetchall()]

    def event_attendees(self, event_id: int) -> list:
        """Return list of attending members for an event."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT m.name, m.email, r.response, r.rsvp_at"
                " FROM rsvps r JOIN members m ON m.id=r.member_id"
                " WHERE r.event_id=? ORDER BY r.rsvp_at",
                (event_id,),
            ).fetchall()
            return [{"name": r[0], "email": r[1], "response": r[2], "rsvp_at": r[3]}
                    for r in rows]

    def status(self) -> dict:
        """High-level statistics."""
        with sqlite3.connect(self.db_path) as conn:
            members = conn.execute("SELECT COUNT(*) FROM members WHERE active=1").fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            rsvps = conn.execute("SELECT COUNT(*) FROM rsvps WHERE response='attending'").fetchone()[0]
        return {"active_members": members, "total_events": events,
                "confirmed_rsvps": rsvps, "db_path": str(self.db_path)}

    def export_data(self) -> dict:
        """Export full dataset as JSON."""
        with sqlite3.connect(self.db_path) as conn:
            members = [Member(*r) for r in conn.execute("SELECT * FROM members").fetchall()]
            events = [Event(*r) for r in conn.execute("SELECT * FROM events").fetchall()]
            rsvps = [RSVP(*r) for r in conn.execute("SELECT * FROM rsvps").fetchall()]
        return {
            "members": [asdict(m) for m in members],
            "events": [asdict(e) for e in events],
            "rsvps": [asdict(r) for r in rsvps],
            "exported_at": datetime.now().isoformat(),
        }


def _status_color(status: str) -> str:
    return {
        "upcoming": CYAN, "active": GREEN, "cancelled": RED, "completed": YELLOW
    }.get(status, NC)


def _fmt_member(m: Member) -> None:
    print(f"  {CYAN}[{m.id}]{NC} {BOLD}{m.name}{NC}  {m.email}  role={YELLOW}{m.role}{NC}")


def _fmt_event(e: Event) -> None:
    sc = _status_color(e.status)
    print(f"  {CYAN}[{e.id}]{NC} {BOLD}{e.title}{NC}  {e.event_date}"
          f"  @ {e.location}  cap={e.capacity}  [{sc}{e.status}{NC}]")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="community_organizer",
        description=f"{BOLD}BlackRoad Community Organizer{NC}",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="System status")
    sub.add_parser("export", help="Export all data as JSON")

    ls = sub.add_parser("list", help="List events or members")
    ls.add_argument("target", choices=["events", "members"], nargs="?", default="events")
    ls.add_argument("--status", default=None)

    am = sub.add_parser("add-member", help="Register a member")
    am.add_argument("name")
    am.add_argument("email")
    am.add_argument("--role", default="member")

    ce = sub.add_parser("add-event", help="Create an event")
    ce.add_argument("title")
    ce.add_argument("date", help="ISO date e.g. 2025-06-01")
    ce.add_argument("--location", default="TBD")
    ce.add_argument("--capacity", type=int, default=50)
    ce.add_argument("--organizer", default=None)

    rv = sub.add_parser("rsvp", help="RSVP to an event")
    rv.add_argument("event_id", type=int)
    rv.add_argument("email")
    rv.add_argument("--response", choices=["attending", "maybe", "declined"], default="attending")

    att = sub.add_parser("attendees", help="List event attendees")
    att.add_argument("event_id", type=int)

    args = parser.parse_args()
    co = CommunityOrganizer()

    if args.cmd == "list":
        if getattr(args, "target", "events") == "events":
            events = co.list_events(args.status)
            label = f"status={args.status}" if args.status else "all"
            print(f"\n{BOLD}{BLUE}Events ({len(events)}) — {label}{NC}")
            [_fmt_event(e) for e in events] or print(f"  {YELLOW}none{NC}")
        else:
            members = co.list_members()
            print(f"\n{BOLD}{BLUE}Members ({len(members)}){NC}")
            [_fmt_member(m) for m in members] or print(f"  {YELLOW}none{NC}")

    elif args.cmd == "add-member":
        m = co.add_member(args.name, args.email, args.role)
        print(f"{GREEN}✓{NC} Member {BOLD}{m.name}{NC} registered (id={m.id})")

    elif args.cmd == "add-event":
        e = co.create_event(args.title, args.date, args.location,
                            capacity=args.capacity, organizer_email=args.organizer)
        print(f"{GREEN}✓{NC} Event {BOLD}{e.title}{NC} created (id={e.id})")

    elif args.cmd == "rsvp":
        r = co.rsvp(args.event_id, args.email, args.response)
        print(f"{GREEN}✓{NC} RSVP recorded (id={r.id}) response={r.response}")

    elif args.cmd == "attendees":
        attendees = co.event_attendees(args.event_id)
        print(f"\n{BOLD}{BLUE}Attendees for event {args.event_id} ({len(attendees)}){NC}")
        for a in attendees:
            rc = GREEN if a["response"] == "attending" else YELLOW
            print(f"  {BOLD}{a['name']}{NC}  {a['email']}  [{rc}{a['response']}{NC}]")

    elif args.cmd == "status":
        st = co.status()
        print(f"\n{BOLD}{BLUE}Community Organizer Status{NC}")
        for k, v in st.items():
            print(f"  {CYAN}{k}{NC}: {GREEN}{v}{NC}")

    elif args.cmd == "export":
        print(json.dumps(co.export_data(), indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
