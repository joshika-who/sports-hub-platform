"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Calendar,
  CheckCircle2,
  Filter,
  Loader2,
  MapPin,
  Search,
  ShieldAlert,
  Sparkles,
  Trophy,
  Users,
} from "lucide-react";
import { apiFetch, formatINR, SportEvent } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const SPORTS = ["All", "Badminton", "Football", "Tennis", "Basketball"];

export default function DiscoveryPage() {
  const { user } = useAuth();
  const [events, setEvents] = useState<SportEvent[]>([]);
  const [sport, setSport] = useState("All");
  const [search, setSearch] = useState("");
  const [eligibleOnly, setEligibleOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (sport !== "All") params.set("sport", sport);
      if (search.trim()) params.set("search", search.trim());
      if (eligibleOnly && user) params.set("eligible_only", "true");
      const query = params.toString() ? `?${params.toString()}` : "";
      const data = await apiFetch<SportEvent[]>(`/api/v1/events${query}`);
      setEvents(data);
    } catch (err: any) {
      setError(err.message || "Failed to load events.");
    } finally {
      setLoading(false);
    }
  }, [sport, search, eligibleOnly, user]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  return (
    <div className="space-y-8">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-slate-900 via-sky-950 to-indigo-950 border border-slate-800 p-6 sm:p-10">
        <div className="max-w-2xl space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-500/15 border border-sky-500/30 text-sky-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            Verified Athlete Passport & One-Click Tournament Entry
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            Discover & Compete in Verified Sports Tournaments
          </h1>
          <p className="text-sm sm:text-base text-slate-300">
            Store your ID, Medical Certificate, and Waiver once in your Document Vault.
            Instantly see events you qualify for, book training courts, follow live WebSocket scores,
            and consult our RAG Injury AI.
          </p>
          <div className="flex flex-wrap gap-3 pt-1">
            {!user ? (
              <Link
                href="/login"
                className="px-5 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-sm transition"
              >
                Sign In with Demo Account
              </Link>
            ) : (
              <Link
                href="/vault"
                className="px-5 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-sm transition"
              >
                Manage Document Vault
              </Link>
            )}
            <Link
              href="/bookings"
              className="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-100 font-semibold text-sm transition"
            >
              Book a Court
            </Link>
          </div>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col lg:flex-row gap-4 items-stretch lg:items-center justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-400 flex items-center gap-1 mr-1">
            <Filter className="w-3.5 h-3.5" /> Sport:
          </span>
          {SPORTS.map((s) => (
            <button
              key={s}
              onClick={() => setSport(s)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition ${
                sport === s
                  ? "bg-sky-500 text-slate-950"
                  : "bg-slate-950 text-slate-300 hover:bg-slate-800 border border-slate-800"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <div className="relative flex-1 sm:w-64">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search title or venue..."
              className="w-full pl-9 pr-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-sky-500"
            />
          </div>

          <label
            className={`flex items-center gap-2.5 px-3.5 py-2 rounded-xl border text-xs font-semibold cursor-pointer select-none transition ${
              eligibleOnly
                ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
                : "bg-slate-950 border-slate-800 text-slate-300"
            } ${!user ? "opacity-50 cursor-not-allowed" : ""}`}
            title={!user ? "Sign in to filter by your personal eligibility" : ""}
          >
            <input
              type="checkbox"
              disabled={!user}
              checked={eligibleOnly}
              onChange={(e) => setEligibleOnly(e.target.checked)}
              className="rounded accent-emerald-500"
            />
            Eligible for me only
          </label>
        </div>
      </div>

      {/* Events Grid */}
      {loading ? (
        <div className="py-16 flex flex-col items-center justify-center gap-3 text-slate-400">
          <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
          <p className="text-sm">Loading upcoming sports events...</p>
        </div>
      ) : error ? (
        <div className="p-6 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm">
          {error}
        </div>
      ) : events.length === 0 ? (
        <div className="py-16 text-center bg-slate-900/50 border border-slate-800 rounded-2xl space-y-3">
          <Trophy className="w-10 h-10 text-slate-600 mx-auto" />
          <div className="font-semibold text-slate-200">No matching events found</div>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            {eligibleOnly
              ? "You may be missing a verified document (such as MEDICAL or WAIVER) required for these events. Visit your Document Vault or untoggle 'Eligible for me only'."
              : "Try clearing your search or selecting another sport."}
          </p>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {events.map((ev) => (
            <div
              key={ev.id}
              className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 flex flex-col justify-between transition group shadow-lg"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="px-2.5 py-1 rounded-lg bg-sky-500/15 text-sky-300 text-xs font-bold uppercase tracking-wider">
                    {ev.sport_name}
                  </span>

                  {user && ev.eligible !== null && ev.eligible !== undefined && (
                    ev.eligible ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-[11px] font-semibold">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Eligible
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 text-[11px] font-semibold">
                        <ShieldAlert className="w-3.5 h-3.5" /> Action Needed
                      </span>
                    )
                  )}
                </div>

                <h2 className="text-lg font-bold text-white group-hover:text-sky-300 transition line-clamp-2">
                  {ev.title}
                </h2>

                <div className="space-y-1.5 text-xs text-slate-400">
                  <div className="flex items-center gap-2">
                    <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    <span className="truncate">{ev.venue}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Calendar className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    <span>{new Date(ev.date_time).toLocaleString()}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Users className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    <span>
                      {ev.registered_count} / {ev.capacity} Registered
                    </span>
                  </div>
                </div>

                <div className="pt-2">
                  <div className="text-[11px] text-slate-500 mb-1.5 font-medium">
                    Mandatory Requirements:
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {ev.mandatory_requirements.length === 0 ? (
                      <span className="text-[11px] text-slate-400">Open to all</span>
                    ) : (
                      ev.mandatory_requirements.map((req) => (
                        <span
                          key={req}
                          className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300"
                        >
                          {req}
                        </span>
                      ))
                    )}
                  </div>
                </div>
              </div>

              <div className="mt-5 pt-4 border-t border-slate-800/80 flex items-center justify-between">
                <div>
                  <div className="text-[10px] uppercase text-slate-500 font-semibold">
                    Entry Fee
                  </div>
                  <div className="text-base font-extrabold text-white">
                    {formatINR(ev.entry_fee)}
                  </div>
                </div>

                <Link
                  href={`/events/${ev.id}`}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs transition"
                >
                  Check Eligibility & Register
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

