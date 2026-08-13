#!/usr/bin/env python3
"""One-off: mirror groups / tickers / theses from a running Fibenchi instance
into another one, over the HTTP API (remote Postgres isn't reachable).

Non-destructive to asset rows + price history: assets are matched by symbol and
created only when missing (Yahoo-validated). Group/thesis *membership* is
reconciled to an exact mirror (adds missing, removes stale extras). Tags are
intentionally NOT touched.

Usage:  python3 scripts/mirror_from_remote.py [--apply]
Without --apply it's a dry run (prints the diff, writes nothing).
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

REMOTE = "http://fibenchi.wstation.lan"
LOCAL = "http://localhost:18000"
TIMEOUT = 35  # Yahoo validation on asset-create can be slow.

APPLY = False


def _req(method: str, base: str, path: str, body=None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            detail = json.loads(raw)
        except Exception:
            detail = raw.decode(errors="replace")
        return e.code, detail


def get(base, path) -> Any:
    status, body = _req("GET", base, path)
    if status != 200:
        sys.exit(f"GET {base}{path} -> {status}: {body}")
    return body


def write(method, base, path, body=None, ok=(200, 201, 204)) -> Any:
    """Mutating request. No-op (logged) unless --apply."""
    if not APPLY:
        print(f"    DRY  {method} {path}  {json.dumps(body) if body else ''}")
        return None
    status, resp = _req(method, base, path, body)
    if status not in ok:
        print(f"    !!   {method} {path} -> {status}: {resp}")
        return None
    return resp


def main():
    print(f"Reading remote: {REMOTE}")
    r_groups = get(REMOTE, "/api/groups")
    r_theses = get(REMOTE, "/api/theses")

    # --- union of every symbol referenced by a remote group or thesis ----------
    union = set()
    for g in r_groups:
        union.update(a["symbol"] for a in g["assets"])
    for t in r_theses:
        union.update(m["symbol"] for m in t["assets"])
    print(f"Remote: {len(r_groups)} groups, {len(r_theses)} theses, {len(union)} distinct symbols")

    # --- 1. ensure every needed asset exists locally; build symbol -> id -------
    local_assets = get(LOCAL, "/api/assets")
    sym_to_id = {a["symbol"].upper(): a["id"] for a in local_assets}
    missing = sorted(s for s in union if s.upper() not in sym_to_id)
    print(f"\n[assets] {len(union)} needed, {len(missing)} missing locally -> creating")
    for sym in missing:
        resp = write("POST", LOCAL, "/api/assets", {"symbol": sym})
        if resp:
            sym_to_id[resp["symbol"].upper()] = resp["id"]
            print(f"    +    {sym} -> id {resp['id']} ({resp.get('type')}, {resp.get('currency')})")
        elif APPLY:
            print(f"    skip {sym}: could not create (Yahoo validation failed?)")

    def ids_for(symbols):
        out, miss = [], []
        for s in symbols:
            i = sym_to_id.get(s.upper())
            (out if i is not None else miss).append(i if i is not None else s)
        return out, miss

    # --- 2. reconcile GROUPS ---------------------------------------------------
    print("\n[groups] reconciling membership to mirror remote")
    local_groups = {g["name"]: g for g in get(LOCAL, "/api/groups")}
    for rg in sorted(r_groups, key=lambda g: g["position"]):
        name = rg["name"]
        lg = local_groups.get(name)
        if lg is None:
            print(f"  create group {name!r}")
            lg = write("POST", LOCAL, "/api/groups",
                       {"name": name, "description": rg.get("description"), "icon": rg.get("icon")})
            if not APPLY:
                continue
            if not lg:
                continue
        gid = lg["id"]
        desired_ids, miss = ids_for([a["symbol"] for a in rg["assets"]])
        current_ids = {a["id"] for a in lg.get("assets", [])}
        to_add = [i for i in desired_ids if i not in current_ids]
        to_remove = [i for i in current_ids if i not in set(desired_ids)]
        flag = f" (skipping unresolved {miss})" if miss else ""
        print(f"  {name:12} have={len(current_ids):2} want={len(desired_ids):2}  +{len(to_add)} -{len(to_remove)}{flag}")
        if to_add:
            write("POST", LOCAL, f"/api/groups/{gid}/assets", {"asset_ids": to_add})
        for aid in to_remove:
            write("DELETE", LOCAL, f"/api/groups/{gid}/assets/{aid}")

    # reorder local groups to match remote position order
    remote_order = [g["name"] for g in sorted(r_groups, key=lambda g: g["position"])]
    fresh = {g["name"]: g["id"] for g in get(LOCAL, "/api/groups")}
    ordered_ids = [fresh[n] for n in remote_order if n in fresh]
    if ordered_ids:
        print(f"  reorder -> {remote_order}")
        write("PUT", LOCAL, "/api/groups/reorder", {"group_ids": ordered_ids})

    # --- 3. reconcile THESES ---------------------------------------------------
    print("\n[theses] reconciling")
    local_theses = {t["name"]: t for t in get(LOCAL, "/api/theses")}
    for rt in r_theses:
        name = rt["name"]
        payload = {
            "name": name,
            "color": rt["color"],
            "description": rt.get("description"),
            "status": rt["status"],
            "opened_at": rt["opened_at"],
        }
        lt = local_theses.get(name)
        if lt is None:
            print(f"  create thesis {name!r}")
            lt = write("POST", LOCAL, "/api/theses", payload)
            if not APPLY:
                continue
            if not lt:
                continue
        else:
            print(f"  update thesis {name!r}")
            write("PUT", LOCAL, f"/api/theses/{lt['id']}",
                  {k: payload[k] for k in ("color", "description", "status", "opened_at")})
        tid = lt["id"]
        desired_ids, miss = ids_for([m["symbol"] for m in rt["assets"]])
        current_ids = {m["id"] for m in lt.get("assets", [])}
        to_add = [i for i in desired_ids if i not in current_ids]
        to_remove = [i for i in current_ids if i not in set(desired_ids)]
        flag = f" (skipping unresolved {miss})" if miss else ""
        print(f"    members have={len(current_ids)} want={len(desired_ids)}  +{len(to_add)} -{len(to_remove)}{flag}")
        if to_add:
            write("POST", LOCAL, f"/api/theses/{tid}/assets", {"asset_ids": to_add})
        for aid in to_remove:
            write("DELETE", LOCAL, f"/api/theses/{tid}/assets/{aid}")

    print("\nDONE" + ("" if APPLY else "  (dry run — re-run with --apply to write)"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually write changes (default: dry run)")
    args = ap.parse_args()
    APPLY = args.apply
    main()
