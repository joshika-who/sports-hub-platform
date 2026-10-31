"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  Loader2,
  Plus,
  Radio,
  RefreshCw,
  ShieldCheck,
  Trophy,
} from "lucide-react";
import { apiFetch, getWsBaseUrl, LiveMatch } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function LiveScoresPage() {
  const { user } = useAuth();
  const [matches, setMatches] = useState<LiveMatch[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [lastEventText, setLastEventText] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  const canReferee = user?.role === "referee" || user?.role === "organizer";

  const loadMatches = useCallback(async () => {
    try {
      const data = await apiFetch<LiveMatch[]>("/api/v1/live/matches");
      setMatches(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMatches();

    // Poll every 5s as a seamless fallback on serverless hosts (like Vercel)
    const pollTimer = setInterval(loadMatches, 5000);

    try {
      const wsBase = getWsBaseUrl();
      if (wsBase) {
        const ws = new WebSocket(`${wsBase}/ws/live`);
        wsRef.current = ws;

        ws.onopen = () => {
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "SCORE_UPDATE" && msg.match) {
              const updated: LiveMatch = msg.match;
              setLastEventText(
                `LIVE UPDATE: ${updated.team_a} ${updated.score_a} - ${updated.score_b} ${updated.team_b}`
              );
              setMatches((prev) => {
                const exists = prev.some((m) => m.id === updated.id);
                if (!exists) return [updated, ...prev];
                return prev.map((m) => (m.id === updated.id ? updated : m));
              });
            }
          } catch {
            // ignore malformed frames
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
        };
      }
    } catch {
      setWsConnected(false);
    }

    return () => {
      clearInterval(pollTimer);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [loadMatches]);

  const handleScoreUpdate = async (
    match: LiveMatch,
    newScoreA: number,
    newScoreB: number,
    newStatus: "SCHEDULED" | "LIVE" | "FINISHED"
  ) => {
    setUpdatingId(match.id);
    try {
      const updated = await apiFetch<LiveMatch>(`/api/v1/live/matches/${match.id}/score`, {
        method: "PUT",
        body: JSON.stringify({
          score_a: Math.max(0, newScoreA),
          score_b: Math.max(0, newScoreB),
          status: newStatus,
        }),
      });
      setMatches((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
      setLastEventText(
        `LIVE UPDATE: ${updated.team_a} ${updated.score_a} - ${updated.score_b} ${updated.team_b}`
      );
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold flex items-center gap-2.5">
            <Activity className="w-7 h-7 text-rose-500" />
            Real-Time Match Center
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Live scoreboard with real-time updates.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-bold border ${
              wsConnected
                ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                : "bg-sky-500/15 text-sky-300 border-sky-500/30"
            }`}
          >
            <Radio className="w-3.5 h-3.5 animate-pulse" />
            {wsConnected ? "Live Stream Connected" : "Live Auto-Sync Active"}
          </span>

          <button
            onClick={loadMatches}
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300"
            title="Refresh matches"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {lastEventText && (
        <div className="p-3 rounded-xl bg-sky-500/15 border border-sky-500/30 text-xs font-bold text-sky-300 flex items-center gap-2">
          <Radio className="w-4 h-4 animate-ping text-sky-400" />
          {lastEventText}
        </div>
      )}

      {canReferee && (
        <div className="p-3.5 rounded-xl bg-indigo-500/15 border border-indigo-500/30 text-xs text-indigo-200 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-indigo-400 shrink-0" />
          <span>
            <strong>Official Scorekeeper Mode Active ({user?.role?.toUpperCase()}):</strong> Use the +1 / Finish controls on any match card below to update live scores.
          </span>
        </div>
      )}

      {loading ? (
        <div className="py-16 flex justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
        </div>
      ) : matches.length === 0 ? (
        <div className="py-16 text-center bg-slate-900 border border-slate-800 rounded-2xl">
          <Trophy className="w-10 h-10 text-slate-600 mx-auto mb-2" />
          <p className="text-sm text-slate-300">No matches scheduled yet.</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 gap-5">
          {matches.map((m) => (
            <div
              key={m.id}
              className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-lg"
            >
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-0.5 rounded bg-sky-500/15 text-sky-300 font-bold uppercase">
                    {m.sport_name || "Sport"}
                  </span>
                  <span className="text-slate-400 truncate max-w-[200px]">
                    {m.event_title}
                  </span>
                </div>

                <span
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                    m.status === "LIVE"
                      ? "bg-rose-500/20 text-rose-300 border border-rose-500/30 animate-pulse"
                      : m.status === "FINISHED"
                      ? "bg-slate-800 text-slate-300"
                      : "bg-amber-500/15 text-amber-300"
                  }`}
                >
                  {m.status} • Court {m.court_number}
                </span>
              </div>

              {/* Scoreboard */}
              <div className="grid grid-cols-7 items-center bg-slate-950 border border-slate-800 rounded-2xl p-4">
                <div className="col-span-3">
                  <div className="font-bold text-sm sm:text-base text-white truncate">
                    {m.team_a}
                  </div>
                  <div className="text-[11px] text-slate-500">Home / Seed A</div>
                </div>

                <div className="col-span-1 flex items-center justify-center gap-2 font-black text-2xl sm:text-3xl text-sky-400">
                  <span>{m.score_a}</span>
                  <span className="text-slate-600 text-lg">:</span>
                  <span>{m.score_b}</span>
                </div>

                <div className="col-span-3 text-right">
                  <div className="font-bold text-sm sm:text-base text-white truncate">
                    {m.team_b}
                  </div>
                  <div className="text-[11px] text-slate-500">Away / Seed B</div>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
                <span>Start: {new Date(m.start_time).toLocaleString()}</span>

                {canReferee && (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <button
                      disabled={updatingId === m.id}
                      onClick={() =>
                        handleScoreUpdate(m, m.score_a + 1, m.score_b, "LIVE")
                      }
                      className="px-2.5 py-1 rounded-lg bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 font-bold flex items-center gap-1"
                    >
                      <Plus className="w-3 h-3" /> {m.team_a.split(" ")[0]}
                    </button>
                    <button
                      disabled={updatingId === m.id}
                      onClick={() =>
                        handleScoreUpdate(m, m.score_a, m.score_b + 1, "LIVE")
                      }
                      className="px-2.5 py-1 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 font-bold flex items-center gap-1"
                    >
                      <Plus className="w-3 h-3" /> {m.team_b.split(" ")[0]}
                    </button>
                    <button
                      disabled={updatingId === m.id}
                      onClick={() =>
                        handleScoreUpdate(
                          m,
                          m.score_a,
                          m.score_b,
                          m.status === "FINISHED" ? "LIVE" : "FINISHED"
                        )
                      }
                      className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold"
                    >
                      {m.status === "FINISHED" ? "Reopen" : "Mark Finished"}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
