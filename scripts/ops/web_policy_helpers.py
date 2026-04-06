#!/usr/bin/env python3
import ipaddress
import re
import time


def parse_csv(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_allow_ips(raw):
    if not raw:
        return [], None
    allow = []
    for entry in parse_csv(raw):
        if entry in ("localhost", "loopback"):
            allow.append(ipaddress.ip_network("127.0.0.1/32"))
            allow.append(ipaddress.ip_network("::1/128"))
            continue
        try:
            allow.append(ipaddress.ip_network(entry, strict=False))
            continue
        except Exception:
            pass
        try:
            addr = ipaddress.ip_address(entry)
            if addr.version == 4:
                allow.append(ipaddress.ip_network(f"{addr}/32"))
            else:
                allow.append(ipaddress.ip_network(f"{addr}/128"))
        except Exception:
            return None, f"invalid_allow_ip:{entry}"
    return allow, None


def normalize_client_ip(addr):
    try:
        ip = ipaddress.ip_address(addr)
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return ip
    except Exception:
        return None


def parse_scopes(raw, all_scopes):
    scopes = {item.lower() for item in parse_csv(raw)}
    if not scopes or "all" in scopes:
        return None, None
    unknown = sorted(scopes - all_scopes)
    if unknown:
        return None, f"invalid_scopes:{','.join(unknown)}"
    return scopes, None


def parse_action_allowlist(raw, all_actions):
    actions = {item.strip().lower() for item in parse_csv(raw)}
    if not actions or "all" in actions:
        return None, None
    unknown = sorted(actions - all_actions)
    if unknown:
        return None, f"invalid_actions:{','.join(unknown)}"
    return actions, None


def parse_action_cooldowns(raw, defaults, all_actions):
    if not raw:
        return dict(defaults), None
    lowered = raw.strip().lower()
    if lowered in ("0", "off", "none", "disable", "disabled"):
        return {}, None
    cooldowns = {}
    for entry in parse_csv(raw):
        if "=" not in entry:
            return None, f"invalid_cooldown:{entry}"
        action, value = [item.strip().lower() for item in entry.split("=", 1)]
        if action not in all_actions:
            return None, f"invalid_cooldown_action:{action}"
        if not value.isdigit():
            return None, f"invalid_cooldown_value:{entry}"
        sec = int(value)
        if sec < 0:
            return None, f"invalid_cooldown_value:{entry}"
        if sec == 0:
            continue
        cooldowns[action] = sec
    return cooldowns, None


def validate_action_scopes(action_allowlist, token_scopes, action_scopes):
    if action_allowlist is None or token_scopes is None:
        return None
    missing = []
    for action in action_allowlist:
        required = action_scopes.get(action)
        if required and required not in token_scopes:
            missing.append(f"{action}:{required}")
    if missing:
        return f"action_scope_mismatch:{','.join(sorted(missing))}"
    return None


def compute_allowed_actions(web_readonly, action_allowlist, all_actions, token_scopes, action_scopes):
    if web_readonly:
        return []
    actions = set(all_actions) if action_allowlist is None else set(action_allowlist)
    if token_scopes is None:
        return sorted(actions)
    allowed = []
    for action in actions:
        required = action_scopes.get(action)
        if required and required in token_scopes:
            allowed.append(action)
    return sorted(allowed)


def check_rate_limit(client_ip, rate_limit_max, rate_limit_window_sec, rate_limit_buckets, rate_limit_lock):
    if rate_limit_max <= 0 or rate_limit_window_sec <= 0:
        return None
    now = time.monotonic()
    with rate_limit_lock:
        bucket = rate_limit_buckets.get(client_ip)
        if bucket is None:
            bucket = []
            rate_limit_buckets[client_ip] = bucket
        cutoff = now - rate_limit_window_sec
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= rate_limit_max:
            retry_after = int(max(1, rate_limit_window_sec - (now - bucket[0])))
            return retry_after
        bucket.append(now)
    return None


def check_action_cooldown(action, action_cooldowns, action_last_run, action_cooldown_lock):
    if not action_cooldowns:
        return None
    cooldown = action_cooldowns.get(action)
    if not cooldown:
        return None
    now = time.monotonic()
    with action_cooldown_lock:
        last = action_last_run.get(action, 0)
        elapsed = now - last if last else None
        if elapsed is not None and elapsed < cooldown:
            return int(max(1, cooldown - elapsed))
        action_last_run[action] = now
    return None


def sanitize_ref(value):
    if not value:
        return ""
    if not re.match(r"^[A-Za-z0-9._/-]+$", value):
        return None
    return value


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    return False


def clamp_int(value, default, min_value, max_value, safe_int):
    number = safe_int(value, default)
    if number < min_value:
        return min_value
    if number > max_value:
        return max_value
    return number


def normalize_host(host, web_allow_remote, web_token, web_require_token):
    value = (host or "").strip()
    if value in ("", "127.0.0.1", "localhost", "::1"):
        return "127.0.0.1", None
    if not web_allow_remote:
        return "127.0.0.1", "remote_blocked"
    if web_require_token and not web_token:
        return None, "token_required"
    return value, None


def is_ip_allowed(client_ip, allow_ips):
    if not allow_ips:
        return True
    ip = normalize_client_ip(client_ip)
    if not ip:
        return False
    for network in allow_ips:
        if ip in network:
            return True
    return False
