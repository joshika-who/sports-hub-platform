"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  CalendarPlus,
  CheckCircle2,
  Cpu,
  Loader2,
  Play,
  Sparkles,
  Wrench,
} from "lucide-react";
import {
  apiFetch,
  SchedulerGenerateResponse,
  SportEvent,
} from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const PRESET_8_TEAMS = [
  "Bangalore Smashers",
  "Hyderabad Falcons",
  "Mumbai Mavericks",
  "Delhi Dynamos",
  "Chennai Aces",
  "Pune Warriors",
  "Kolkata Knights",
  "Goa Mariners",
];

const PRESET_6_TEAMS = [
  "Alpha Strikers",
  "Bravo United",
  "Charlie Chargers",
  "Delta Royals",
  "Echo Titans",
  "Foxtrot Rangers",
];

export default function OrganizerPage() {
  const { user, refreshNotifications } = useAuth();
  const [events, setEvents] = useState<SportEvent[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string>("");

  // Create Event state
  const [sportName, setSportName] = useState("Badminton");
  const [title, setTitle] = useState("");
  const [venue, setVenue] = useState("Smash Arena Indoor Stadium");
  const [entryFeeRupees, setEntryFeeRupees] = useState(500);
  const [capacity, setCapacity] = useState(16);
  const [reqsText, setReqsText] = useState("MIN_AGE:18, ID, MEDICAL");
  const [creatingEvent, setCreatingEvent] = useState(false);

  // Scheduler state
  const [teamsText, setTeamsText] = useState(PRESET_8_TEAMS.join("\n"));
  const [numCourts, setNumCourts] = useState(2);
  const [durationMins, setDurationMins] = useState(60);
  const [minRestSlots, setMinRestSlots] = useState(1);
  const [format, setFormat] = useState<"round_robin" | "single_elimination">(
    "single_elimination"
  );
  const [scheduleResult, setScheduleResult] =
    useState<SchedulerGenerateResponse | null>(null);
  const [solving, setSolving] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadEvents = async () => {
    try {
      const list = await apiFetch<SportEvent[]>("/api/v1/events");
      setEvents(list);
      if (list.length > 0 && !selectedEventId) {
        setSelectedEventId(list[0].id);
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    loadEvents();
  }, []);

  const handleCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingEvent(true);
    setError(null);
    setMessage(null);
    try {
      const reqList = reqsText
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const futureDate = new Date(Date.now() + 7 * 86400000).toISOString();
      const created = await apiFetch<SportEvent>("/api/v1/events", {
        method: "POST",
        body: JSON.stringify({
          sport_name: sportName,
          title,
          venue,
          date_time: futureDate,
          entry_fee: Math.round(Number(entryFeeRupees) * 100),
          capacity: Number(capacity),
          mandatory_requirements: reqList,
        }),
      });
      setMessage(`Event "${created.title}" created!`);
      setTitle("");
      await loadEvents();
      setSelectedEventId(created.id);
    } catch (err: any) {
      setError(err.message || "Failed to create event (requires Organizer role).");
    } finally {
      setCreatingEvent(false);
    }
  };

  const buildSchedulerPayload = () => {
    const teams = teamsText
      .split("\n")
      .map((t) => t.trim())
      .filter(Boolean);
    const start = new Date(Date.now() + 86400000);
    start.setMinutes(0, 0, 0);
    return {
      teams,
      num_courts: Number(numCourts),
      match_duration_minutes: Number(durationMins),
      start_time: start.toISOString(),
      min_rest_slots: Number(minRestSlots),
      format,
    };
  };

  const handleGeneratePreview = async (e: React.FormEvent) => {
    e.preventDefault();
    setSolving(true);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch<SchedulerGenerateResponse>(
        "/api/v1/scheduler/generate",
        {
          method: "POST",
          body: JSON.stringify(buildSchedulerPayload()),
        }
      );
      setScheduleResult(res);
      setMessage(
        `OR-Tools CP-SAT Solver (${res.solver_status}): Generated ${res.total_matches} conflict-free matches across ${res.makespan_slots} slots.`
      );
    } catch (err: any) {
      setError(err.message || "Constraint solver failed.");
    } finally {
      setSolving(false);
    }
  };

  const handleCommitSchedule = async () => {
    if (!selectedEventId) return;
    setCommitting(true);
    setError(null);
    setMessage(null);
    try {
      const committed = await apiFetch<any[]>(
        `/api/v1/scheduler/generate/${selectedEventId}/commit`,
        {
          method: "POST",
          body: JSON.stringify(buildSchedulerPayload()),
        }
      );
      await refreshNotifications();
      setMessage(
        `Committed ${committed.length} matches to tournament & dispatched MATCH_SCHEDULE_UPDATED notifications!`
      );
    } catch (err: any) {
      setError(
        err.message ||
          "Commit failed (ensure you are signed in as organizer@demo.com)."
      );
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold flex items-center gap-2.5">
            <Wrench className="w-7 h-7 text-sky-400" />
            Organizer Command Center & CP-SAT Scheduler
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Create tournaments with automated Vault eligibility rules and generate conflict-free timetables using Google OR-Tools CP-SAT.
          </p>
        </div>

        {user?.role !== "organizer" && (
          <Link
            href="/login"
            className="px-4 py-2 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-300 text-xs font-bold"
          >
            Sign in as organizer@demo.com to Commit Changes
          </Link>
        )}
      </div>

      {message && (
        <div className="p-3.5 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-xs text-emerald-300">
          {message}
        </div>
      )}
      {error && (
        <div className="p-3.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-xs text-rose-300">
          {error}
        </div>
      )}

      <div className="grid lg:grid-cols-12 gap-6">
        {/* Create Event Card */}
        <form
          onSubmit={handleCreateEvent}
          className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 h-fit"
        >
          <div className="flex items-center gap-2 font-bold text-base text-white">
            <CalendarPlus className="w-5 h-5 text-sky-400" />
            Create New Tournament Event
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-300 mb-1">Sport</label>
              <select
                value={sportName}
                onChange={(e) => setSportName(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
              >
                <option value="Badminton">Badminton</option>
                <option value="Football">Football</option>
                <option value="Tennis">Tennis</option>
                <option value="Basketball">Basketball</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-300 mb-1">
                Entry Fee (₹ INR)
              </label>
              <input
                type="number"
                min={0}
                value={entryFeeRupees}
                onChange={(e) => setEntryFeeRupees(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-300 mb-1">Event Title</label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. National Inter-Club Badminton Cup"
              className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="block text-xs text-slate-300 mb-1">Venue</label>
              <input
                type="text"
                required
                value={venue}
                onChange={(e) => setVenue(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-300 mb-1">Capacity</label>
              <input
                type="number"
                min={2}
                value={capacity}
                onChange={(e) => setCapacity(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-300 mb-1">
              Mandatory Vault Requirements (comma-separated)
            </label>
            <input
              type="text"
              value={reqsText}
              onChange={(e) => setReqsText(e.target.value)}
              placeholder="MIN_AGE:18, ID, MEDICAL, WAIVER"
              className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-sky-300"
            />
          </div>

          <button
            type="submit"
            disabled={creatingEvent}
            className="w-full py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 transition"
          >
            {creatingEvent ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Publish Event
          </button>
        </form>

        {/* OR-Tools CP-SAT Scheduler */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 font-bold text-base">
              <Cpu className="w-5 h-5 text-sky-400" />
              Google OR-Tools CP-SAT Tournament Scheduler
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setTeamsText(PRESET_8_TEAMS.join("\n"));
                  setNumCourts(2);
                  setFormat("single_elimination");
                }}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-[11px] font-semibold text-sky-300 flex items-center gap-1"
              >
                <Sparkles className="w-3 h-3" /> Preset: 8 Teams / 2 Courts
              </button>
              <button
                type="button"
                onClick={() => {
                  setTeamsText(PRESET_6_TEAMS.join("\n"));
                  setNumCourts(3);
                  setFormat("round_robin");
                }}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-[11px] font-semibold text-emerald-300 flex items-center gap-1"
              >
                <Sparkles className="w-3 h-3" /> Preset: 6 Teams / 3 Courts (Round Robin)
              </button>
            </div>
          </div>

          <form onSubmit={handleGeneratePreview} className="space-y-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-slate-300 mb-1">
                  Teams (one per line)
                </label>
                <textarea
                  rows={6}
                  value={teamsText}
                  onChange={(e) => setTeamsText(e.target.value)}
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-white"
                />
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-slate-300 mb-1">
                    Target Tournament Event
                  </label>
                  <select
                    value={selectedEventId}
                    onChange={(e) => setSelectedEventId(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                  >
                    {events.map((ev) => (
                      <option key={ev.id} value={ev.id}>
                        {ev.title} ({ev.sport_name})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="block text-xs text-slate-300 mb-1">Format</label>
                    <select
                      value={format}
                      onChange={(e) => setFormat(e.target.value as any)}
                      className="w-full px-2.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                    >
                      <option value="round_robin">Round Robin</option>
                      <option value="single_elimination">Single Elimination</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs text-slate-300 mb-1">Courts</label>
                    <input
                      type="number"
                      min={1}
                      max={12}
                      value={numCourts}
                      onChange={(e) => setNumCourts(Number(e.target.value))}
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="block text-xs text-slate-300 mb-1">
                      Match Duration (min)
                    </label>
                    <input
                      type="number"
                      min={15}
                      max={180}
                      value={durationMins}
                      onChange={(e) => setDurationMins(Number(e.target.value))}
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-300 mb-1">
                      Min Rest Slots
                    </label>
                    <input
                      type="number"
                      min={0}
                      max={5}
                      value={minRestSlots}
                      onChange={(e) => setMinRestSlots(Number(e.target.value))}
                      className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="submit"
                disabled={solving}
                className="px-5 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition"
              >
                {solving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                Solve Conflict-Free Timetable
              </button>

              {scheduleResult && (
                <button
                  type="button"
                  disabled={committing}
                  onClick={handleCommitSchedule}
                  className="px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition"
                >
                  {committing ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4" />
                  )}
                  Commit Schedule & Notify Athletes
                </button>
              )}
            </div>
          </form>

          {scheduleResult && (
            <div className="space-y-3 pt-2 border-t border-slate-800">
              <div className="flex flex-wrap items-center justify-between text-xs text-slate-300">
                <span>
                  Status:{" "}
                  <strong className="text-emerald-400">
                    {scheduleResult.solver_status}
                  </strong>{" "}
                  • Matches: <strong>{scheduleResult.total_matches}</strong> •
                  Makespan: <strong>{scheduleResult.makespan_slots} slots</strong>
                </span>
              </div>

              <div className="overflow-x-auto rounded-xl border border-slate-800">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 text-slate-400 uppercase text-[10px]">
                    <tr>
                      <th className="py-2.5 px-3">#</th>
                      <th className="py-2.5 px-3">Slot</th>
                      <th className="py-2.5 px-3">Court</th>
                      <th className="py-2.5 px-3">Matchup</th>
                      <th className="py-2.5 px-3">Start Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70">
                    {scheduleResult.timetable.map((item) => (
                      <tr key={item.match_index} className="hover:bg-slate-950/60">
                        <td className="py-2 px-3 font-mono text-slate-400">
                          {item.match_index}
                        </td>
                        <td className="py-2 px-3">
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-sky-300 font-mono">
                            Slot {item.slot_index + 1}
                          </span>
                        </td>
                        <td className="py-2 px-3 font-semibold text-emerald-400">
                          Court {item.court_number}
                        </td>
                        <td className="py-2 px-3 font-bold text-white">
                          {item.team_a}{" "}
                          <span className="text-slate-500 font-normal">vs</span>{" "}
                          {item.team_b}
                        </td>
                        <td className="py-2 px-3 text-slate-400">
                          {new Date(item.start_time).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

