# Post-Attach Checklist

Use this checklist after you register Apple Notes Snapshot with a local host.

1. Confirm the host can launch `"/absolute/path/to/notesctl" "mcp"` on the same machine.
2. Confirm the host sees the v1 read-only tools:
   - `get_status`
   - `run_doctor`
   - `verify_freshness`
   - `get_log_health`
   - `list_recent_runs`
   - `get_access_policy`
3. Confirm the host can read the v1 resources:
   - `notes-snapshot://state.json`
   - `notes-snapshot://summary.txt`
   - `notes-snapshot://recent-runs`
   - `notes-snapshot://config-safe-summary`
4. Run `./notesctl status --json` locally and compare it with the host-visible `get_status` output.
5. If the host attach succeeds but returns a first-run or missing-state view, initialize the local snapshot loop before treating that as an MCP failure.
6. If you are using the Local Web API instead of MCP, start with:
   - `GET /api/status`
   - `GET /api/recent-runs?tail=5`
   - `GET /api/access`
7. Treat host-side menus, config paths, or extra options as host-owned details. Re-check the current host docs before you claim full support.
