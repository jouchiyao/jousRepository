"""访问控制与防滥用：Supabase 持久计数 + 本地文件降级。

每个访客 = IP + User-Agent 哈希，普通访客永久限 2 次；管理员不限。
Supabase 不可用时自动降级为本地 JSON 存储，并提示限制可能不跨实例/设备。
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from utils.config import get_env

FREE_LIMIT = 2


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_visitor_id(ip: str, user_agent: str) -> str:
    """IP + UA → 稳定匿名 ID（哈希）。"""
    raw = f"{ip}|{user_agent}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def get_client_info() -> tuple[str, str, str]:
    """从 Streamlit 上下文读取客户端 IP / UA，返回 (visitor_id, ip, ua)。"""
    ip = "unknown"
    ua = "unknown"
    try:
        import streamlit as st

        headers = {}
        try:
            headers = dict(st.context.headers or {})
        except Exception:  # noqa: BLE001
            headers = {}
        ip = headers.get("X-Forwarded-For") or headers.get("X-Real-IP") or "unknown"
        if ip and "," in str(ip):
            ip = str(ip).split(",")[0].strip()
        ua = headers.get("User-Agent") or "unknown"
    except Exception:  # noqa: BLE001
        pass
    return get_visitor_id(str(ip), str(ua)), str(ip), str(ua)


class VisitorTracker:
    """访问计数。优先 Supabase，失败自动降级本地文件。"""

    def __init__(self) -> None:
        self.mode = "local"
        self.last_error = ""
        self._lock = threading.Lock()
        self._supabase = None
        self.fallback_path = Path(get_env("VISITOR_FALLBACK_FILE", "data/visitors.json"))
        try:
            self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:  # noqa: BLE001
            pass
        url = get_env("SUPABASE_URL")
        key = get_env("SUPABASE_KEY")
        if url and key:
            try:
                from supabase import create_client  # 懒加载：未安装时自动降级

                self._supabase = create_client(url, key)
                self.mode = "supabase"
            except Exception as exc:  # noqa: BLE001
                self.mode = "local"
                self.last_error = f"Supabase 初始化失败：{exc}"

    # ---------- 本地文件存储 ----------
    def _read_local(self) -> dict[str, Any]:
        with self._lock:
            if not self.fallback_path.exists():
                return {}
            try:
                return json.loads(self.fallback_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                return {}

    def _write_local(self, data: dict[str, Any]) -> None:
        with self._lock:
            tmp = self.fallback_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.fallback_path)

    # ---------- 计数查询 ----------
    def get_visit_count(self, visitor_id: str) -> int:
        if self.mode == "supabase" and self._supabase is not None:
            try:
                resp = (
                    self._supabase.table("visitors")
                    .select("visit_count")
                    .eq("visitor_id", visitor_id)
                    .limit(1)
                    .execute()
                )
                rows = resp.data or []
                if rows:
                    return int(rows[0].get("visit_count", 0))
                return 0
            except Exception as exc:  # noqa: BLE001
                self.mode = "local"
                self.last_error = f"Supabase 查询失败，已降级本地：{exc}"
        data = self._read_local()
        return int(data.get(visitor_id, {}).get("visit_count", 0))

    def _increment_remote(self, visitor_id: str) -> None:
        now = _now_iso()
        current = self.get_visit_count(visitor_id)
        if current > 0:
            self._supabase.table("visitors").update(
                {"visit_count": current + 1, "last_visit": now}
            ).eq("visitor_id", visitor_id).execute()
        else:
            self._supabase.table("visitors").insert(
                {
                    "visitor_id": visitor_id,
                    "visit_count": 1,
                    "first_visit": now,
                    "last_visit": now,
                }
            ).execute()

    def _increment_local(self, visitor_id: str) -> dict[str, Any]:
        now = _now_iso()
        data = self._read_local()
        entry = data.get(visitor_id, {"first_visit": now})
        entry["visit_count"] = int(entry.get("visit_count", 0)) + 1
        entry["last_visit"] = now
        data[visitor_id] = entry
        self._write_local(data)
        return entry

    def record_execution(self, visitor_id: str) -> dict[str, Any]:
        """每次成功分析后调用，计数 +1。返回最新记录。"""
        if self.mode == "supabase" and self._supabase is not None:
            try:
                self._increment_remote(visitor_id)
                return {"visitor_id": visitor_id, "visit_count": self.get_visit_count(visitor_id)}
            except Exception as exc:  # noqa: BLE001
                self.mode = "local"
                self.last_error = f"Supabase 写入失败，已降级本地：{exc}"
        try:
            entry = self._increment_local(visitor_id)
            return {"visitor_id": visitor_id, **entry}
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"本地存储写入失败（计数仅本次会话生效）：{exc}"
            return {
                "visitor_id": visitor_id,
                "visit_count": self.get_visit_count(visitor_id) + 1,
                "warning": self.last_error,
            }

    def can_execute(self, visitor_id: str) -> tuple[bool, int, str]:
        """返回 (是否允许, 剩余次数, 提示)。"""
        try:
            count = self.get_visit_count(visitor_id)
            remaining = max(0, FREE_LIMIT - count)
            if count >= FREE_LIMIT:
                return False, remaining, "您已达到免费使用上限（2次），请联系管理员"
            return True, remaining, f"本会话可用次数：{remaining}/2"
        except Exception as exc:  # noqa: BLE001
            self.mode = "local"
            self.last_error = str(exc)
            count = self.get_visit_count(visitor_id)
            remaining = max(0, FREE_LIMIT - count)
            return count < FREE_LIMIT, remaining, f"计数服务异常，已降级本地：{self.last_error}"

    # ---------- 管理员查看 ----------
    def list_visitors(self) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        if self.mode == "supabase" and self._supabase is not None:
            try:
                resp = self._supabase.table("visitors").select("*").order("last_visit", desc=True).execute()
                rows = resp.data or []
            except Exception as exc:  # noqa: BLE001
                self.last_error = f"Supabase 读取失败，已降级本地：{exc}"
                self.mode = "local"
        if not rows and self.mode == "local":
            data = self._read_local()
            rows = []
            for vid, entry in data.items():
                rows.append(
                    {
                        "visitor_id": vid,
                        "visit_count": int(entry.get("visit_count", 0)),
                        "first_visit": entry.get("first_visit", ""),
                        "last_visit": entry.get("last_visit", ""),
                    }
                )
            rows.sort(key=lambda r: r.get("last_visit", ""), reverse=True)
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(columns=["visitor_id", "visit_count", "first_visit", "last_visit"])
        return df
