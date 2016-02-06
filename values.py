"""Script intended to periodically pull account values and store them"""

import logging
import os
import sqlite3
import time

import pcap


def store_values(values):
    """Store a current snapshot of account values"""
    db_path = os.path.join(pcap.CONF_DIR, "pcap.db")

    conn = None

    try:
        conn = sqlite3.connect(db_path)
        _init_db(conn)

        if values is None or len(values) == 0:
            raise Exception("No account values to record? (values=%s)"
                            % values)

        c = conn.cursor()
        now = int(time.time())
        c.execute("INSERT INTO snapshots (created_at) VALUES (?)", (now,))
        snapshot = c.execute("SELECT * FROM snapshots ORDER BY id desc "
                             "LIMIT 1").fetchone()
        sid, created_at = snapshot
        assert created_at == now

        for account in values:
            c.execute("""INSERT INTO balances
                (snapshot_id, name, detail, type, balance)
                VALUES (?, ?, ?, ?, ?)""",
                (sid, account.name, account.detail, account.type,
                 account.balance))  # NOQA

        c.close()
        conn.commit()

    finally:
            conn.close()


def _init_db(conn):
    """Make sure schema is installed."""

    # store each set of values with an associated snapshot
    # id to represent a single pull
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    # verify sqlite3 was compiled with FK support
    fk_enabled, = c.execute("PRAGMA foreign_keys").fetchone()
    assert fk_enabled == 1

    c.execute("""
        CREATE TABLE IF NOT EXISTS snapshots
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                created_at INT NOT NULL
            )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS balances
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                name TEXT NOT NULL,
                detail TEXT NOT NULL,
                type TEXT NOT NULL,
                balance REAL NOT NULL,
                snapshot_id INT NOT NULL,
                FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
            )
    """)
    c.close()


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger('selenium').setLevel(logging.INFO)

    p = pcap.PersonalCapital()
    p.login()
    values = p.accounts()

    store_values(values)
