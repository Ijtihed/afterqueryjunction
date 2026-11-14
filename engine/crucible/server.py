"""HTTP front for an Episode. The episode, its seed and its journal live only
in this process; clients see observations and nothing else."""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .episode import DEFAULT_SALT, ActionError, Episode

MAX_BODY = 64 * 1024
LOCK = threading.Lock()


class Session:
    def __init__(self, seed: int, salt: str, journal_path: str, meta: dict | None = None, lab_budget: int = 0):
        self.ep = Episode(seed, salt, lab_budget=lab_budget)
        self.path = journal_path
        self.meta = meta or {}
        os.makedirs(os.path.dirname(journal_path) or ".", exist_ok=True)
        with open(journal_path, "w", encoding="utf-8"):
            pass
        self.written = 0

    def flush(self):
        new = self.ep.journal[self.written:]
        if not new:
            return
        with open(self.path, "a", encoding="utf-8") as f:
            for e in new:
                if self.meta.get("timestamps"):
                    e = dict(e, ts=round(time.time(), 3))
                f.write(json.dumps(e, separators=(",", ":")) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.written = len(self.ep.journal)


class App:
    def __init__(self, args):
        self.args = args
        self.sessions: dict = {}
        if not args.play:
            self.sessions["default"] = Session(args.seed, args.salt, os.path.join(args.data, "journal.jsonl"), lab_budget=args.lab_runs)

    def session(self, body: dict) -> Session:
        sid = body.get("session", "default")
        if not isinstance(sid, str) or sid not in self.sessions:
            raise ActionError("unknown session")
        return self.sessions[sid]

    def handle(self, cmd: str, body: dict) -> dict:
        if cmd == "new_session":
            if not self.args.play:
                raise ActionError("not available")
            seed = body.get("seed")
            if not isinstance(seed, int) or isinstance(seed, bool):
                raise ActionError("seed must be an integer")
            player = "".join(c for c in str(body.get("player", "anon"))[:24] if c.isalnum() or c in "-_") or "anon"
            sid = f"{time.strftime('%Y%m%d-%H%M%S')}-{player}-s{seed}"
            s = Session(seed, self.args.salt, os.path.join(self.args.data, "sessions", sid + ".jsonl"), {"timestamps": True}, lab_budget=self.args.lab_runs)
            self.sessions[sid] = s
            return {"session": sid, "seed": seed}
        s = self.session(body)
        ep = s.ep
        if cmd == "note" and self.args.play:
            text = json.dumps({"ts": round(time.time(), 3), "kind": str(body.get("kind", ""))[:40],
                               "text": str(body.get("text", ""))[:2000]})
            with open(s.path.replace(".jsonl", ".notes.jsonl"), "a", encoding="utf-8") as f:
                f.write(text + "\n")
            return {"ok": True}
        try:
            if cmd == "brief":
                return ep.brief()
            if cmd == "view":
                return ep.view(_idx(body))
            if cmd == "lab":
                return ep.lab(body.get("rows"))
            if cmd == "open":
                return ep.open(_idx(body), body.get("gate"))
            if cmd == "close":
                return ep.close(_idx(body))
            if cmd == "frames":
                every = body.get("every", 1)
                if not isinstance(every, int) or isinstance(every, bool) or not 1 <= every <= 1000:
                    raise ActionError("every must be 1..1000")
                if body.get("kind") == "lab":
                    key = ("lab", body.get("run"))
                else:
                    key = ("chamber", body.get("chamber"), body.get("step"))
                fr = ep.frames(key, every)
                legend = {m["symbol"]: m for m in (ep.substance(i) for i in ep.skin.symbol)}
                return {"frames": fr, "legend": legend if body.get("legend") else None}
            if cmd == "status":
                sc = ep.score()
                return {"lab_runs_left": ep.brief()["lab"]["runs_left"],
                        "chambers": [{k: c[k] for k in ("objectives_met", "objectives", "complete", "gates_opened")}
                                     for c in sc["chambers"]]}
            if cmd == "score" and self.args.play:
                return ep.score()
            raise ActionError("unknown command")
        finally:
            s.flush()


def _idx(body: dict) -> int:
    c = body.get("chamber")
    if not isinstance(c, int) or isinstance(c, bool):
        raise ActionError("chamber must be an integer")
    return c - 1


def make_handler(app: App, web_root: str | None):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code: int, payload: bytes, ctype: str = "application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, b'{"ok":true}')
            if web_root:
                rel = self.path.split("?")[0].lstrip("/") or "index.html"
                full = os.path.realpath(os.path.join(web_root, rel))
                if full.startswith(os.path.realpath(web_root) + os.sep) and os.path.isfile(full):
                    ctype = {"html": "text/html", "js": "text/javascript", "css": "text/css",
                             "json": "application/json"}.get(full.rsplit(".", 1)[-1], "application/octet-stream")
                    with open(full, "rb") as f:
                        return self._send(200, f.read(), ctype + "; charset=utf-8")
            self._send(404, b'{"error":"not found"}')

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                n = -1
            if n < 0 or n > MAX_BODY:
                self.close_connection = True
                return self._send(413, b'{"error":"request too large"}')
            raw = self.rfile.read(n)
            if not self.path.startswith("/api/"):
                return self._send(404, b'{"error":"not found"}')
            try:
                body = json.loads(raw or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except (ValueError, RecursionError):
                return self._send(400, b'{"error":"body must be a JSON object"}')
            try:
                with LOCK:
                    out = app.handle(self.path[5:], body)
                self._send(200, json.dumps(out).encode())
            except ActionError as e:
                self._send(400, json.dumps({"error": str(e)}).encode())
            except Exception:
                self._send(500, b'{"error":"internal error"}')

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=int(os.environ.get("CRUCIBLE_SEED", "1")))
    ap.add_argument("--salt", default=os.environ.get("CRUCIBLE_SALT", DEFAULT_SALT))
    ap.add_argument("--data", default=os.environ.get("CRUCIBLE_DATA", "/var/crucible"))
    ap.add_argument("--lab-runs", type=int, default=int(os.environ.get("CRUCIBLE_LAB_RUNS", "0")), help="lab budget; 0 = default")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--play", action="store_true", help="human playtest mode: sessions, web UI, score endpoint")
    ap.add_argument("--web", default=None)
    args = ap.parse_args()
    app = App(args)
    srv = ThreadingHTTPServer((args.host, args.port), make_handler(app, args.web))
    srv.daemon_threads = True
    print(f"crucible listening on {args.host}:{args.port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
