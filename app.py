"""REST APP to expose current account values"""

import json
import sqlite3

import flask

import pcap
from values import DB_PATH

app = flask.Flask(__name__)


@app.route('/')
def index():
    # quick n' dirty api key check
    cfg = pcap.read_config()
    apikey = cfg.get('DEFAULT', 'apikey')
    if not apikey:
        raise Exception("No apikey in config")

    req_apikey = flask.request.headers.get('apikey')
    if apikey != req_apikey:
        flask.abort(401)

    # pass back a diction of account value information
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM snapshots ORDER BY `id` DESC LIMIT 1")
        row = cursor.fetchone()
        snapshot_id, created_at = row

        # now fetch all the account values for this snapshot
        cursor.execute("SELECT * FROM balances WHERE snapshot_id=?",
                       (snapshot_id,))
        results = _fetchall_as_dicts(cursor)
        cursor.close()

    finally:
        if conn:
            conn.close()

    # pass back the account values as well as the snapshot time
    d = {
        "snapshot": {
            "id": snapshot_id,
            "created_at": created_at,
        },

        "accounts": results
    }
    return json.dumps(d, indent=4, sort_keys=True)


def _fetchall_as_dicts(cursor):
    # translate rows to a list of dicts for easier access:
    results = []

    rows = cursor.fetchall()
    for row in rows:
        d = {}
        for i, col in enumerate(cursor.description):
            d[col[0]] = row[i]

        results.append(d)

    return results


if __name__ == '__main__':
    app.run(debug=True)
