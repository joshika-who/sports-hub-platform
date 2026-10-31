"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Bell, Check, CheckCheck, Loader2 } from "lucide-react";
import { apiFetch, NotificationItem } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function NotificationsPage() {
  const { user, refreshNotifications } = useAuth();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadNotifications = useCallback(async () => {
    if (!user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const list = await apiFetch<NotificationItem[]>("/api/v1/notifications/me");
      setItems(list);
      await refreshNotifications();
    } finally {
      setLoading(false);
    }
  }, [user, refreshNotifications]);

  useEffect(() => {
    loadNotifications();
  }, [loadNotifications]);

  const markRead = async (id: string) => {
    await apiFetch(`/api/v1/notifications/${id}/read`, { method: "POST" });
    await loadNotifications();
  };

  const markAllRead = async () => {
    await apiFetch("/api/v1/notifications/read-all", { method: "POST" });
    await loadNotifications();
  };

  if (!user) {
    return (
      <div className="p-8 rounded-2xl bg-slate-900 border border-slate-800 text-center space-y-4">
        <Bell className="w-10 h-10 text-sky-400 mx-auto" />
        <h2 className="text-lg font-bold">Sign in to view your notifications</h2>
        <Link
          href="/login"
          className="inline-block px-5 py-2.5 rounded-xl bg-sky-500 text-slate-950 font-bold text-xs"
        >
          Sign In
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold flex items-center gap-2">
            <Bell className="w-6 h-6 text-sky-400" />
            Push & In-App Notifications
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Dispatched via FCM / APNs dispatcher (logged & stored in `notifications` table in mock mode).
          </p>
        </div>

        {items.some((i) => !i.read) && (
          <button
            onClick={markAllRead}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold text-sky-300 flex items-center gap-1.5"
          >
            <CheckCheck className="w-4 h-4" /> Mark All Read
          </button>
        )}
      </div>

      {loading ? (
        <div className="py-12 flex justify-center">
          <Loader2 className="w-7 h-7 animate-spin text-sky-400" />
        </div>
      ) : items.length === 0 ? (
        <div className="p-12 rounded-2xl bg-slate-900 border border-slate-800 text-center text-xs text-slate-400">
          No notifications yet.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((n) => (
            <div
              key={n.id}
              className={`p-4 rounded-2xl border transition flex items-start justify-between gap-4 ${
                n.read
                  ? "bg-slate-900/60 border-slate-800/80 text-slate-300"
                  : "bg-slate-900 border-sky-500/40 text-white shadow-lg"
              }`}
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono text-[10px] font-bold">
                    {n.kind}
                  </span>
                  <span className="font-bold text-sm">{n.title}</span>
                  {!n.read && (
                    <span className="w-2 h-2 rounded-full bg-sky-400" />
                  )}
                </div>
                <p className="text-xs text-slate-300">{n.body}</p>
                <div className="text-[10px] text-slate-500">
                  {new Date(n.sent_at).toLocaleString()}
                </div>
              </div>

              {!n.read && (
                <button
                  onClick={() => markRead(n.id)}
                  className="shrink-0 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-sky-300 flex items-center gap-1"
                >
                  <Check className="w-3.5 h-3.5" /> Read
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

