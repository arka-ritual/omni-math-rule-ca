#!/usr/bin/env python3
"""Terminate every live Modal Sandbox created by the SWE-Bench Pro driver.

Modal bills sandboxes for wall-clock time, so a leaked sandbox keeps costing
money until something kills it. `ModalSandboxEnvironmentWithAbstain` terminates
its own sandbox on the normal path and every sandbox carries a server-side
lifetime cap, but neither helps if the driver is hard-killed and you want the
meter to stop *now*.

This is the backstop. It is safe to run at any time — it only touches sandboxes
in the driver's own App (`swebench-pro-ca` by default), never anything else in
your Modal workspace.

Usage:
    python swebench_pro/scripts/modal_teardown.py              # terminate all
    python swebench_pro/scripts/modal_teardown.py --dry-run    # just list them
    python swebench_pro/scripts/modal_teardown.py --app other-app

Wired into `swebench_pro/run_r0.sh` as an EXIT/INT/TERM trap, so a Ctrl-C
during a sweep cleans up on the way out.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from swebench_pro.modal_runtime import ALL_APP_NAMES, list_sandboxes, terminate_all  # noqa: E402


def sweep(app: str, dry_run: bool) -> tuple[int, int]:
    """Returns (killed, still_live)."""
    try:
        live = list_sandboxes(app)
    except Exception as e:
        # Never let a teardown failure mask the real error in a trap context.
        print(f"[teardown] could not list sandboxes in app '{app}': {e}")
        return 0, 0

    if not live:
        print(f"[teardown] no live sandboxes in app '{app}'.")
        return 0, 0

    print(f"[teardown] {len(live)} live sandbox(es) in app '{app}':")
    for sb in live:
        print(f"    {sb.object_id}")

    if dry_run:
        print("[teardown] --dry-run: nothing terminated.")
        return 0, len(live)

    killed = terminate_all(app)
    print(f"[teardown] terminated {len(killed)} sandbox(es) in '{app}'.")

    remaining = list_sandboxes(app)
    if remaining:
        print(f"[teardown] WARNING: {len(remaining)} still live in '{app}': "
              f"{', '.join(sb.object_id for sb in remaining)}")
    return len(killed), len(remaining)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", action="append", default=None,
                    help=f"Modal App to sweep; repeat for several. "
                         f"Default: {' and '.join(ALL_APP_NAMES)}")
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would be terminated without terminating it.")
    args = ap.parse_args()

    apps = args.app or ALL_APP_NAMES
    total_killed = total_left = 0
    for app in apps:
        k, left = sweep(app, args.dry_run)
        total_killed += k
        total_left += left

    if args.dry_run:
        return 0
    if total_left:
        print(f"[teardown] WARNING: {total_left} sandbox(es) still live.")
        return 1
    print(f"[teardown] all apps clean ({total_killed} terminated).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
