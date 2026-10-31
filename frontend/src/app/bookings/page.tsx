"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Calendar,
  CheckCircle2,
  Clock,
  Loader2,
  Lock,
  MapPin,
} from "lucide-react";
import {
  apiFetch,
  BookingItem,
  Court,
  formatINR,
  SlotAvailability,
} from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import PaymentModal from "@/components/PaymentModal";

export default function BookingsPage() {
  const { user } = useAuth();
  const [courts, setCourts] = useState<Court[]>([]);
  const [selectedCourt, setSelectedCourt] = useState<Court | null>(null);
  const [dateStr, setDateStr] = useState<string>(() => {
    const tomorrow = new Date(Date.now() + 86400000);
    return tomorrow.toISOString().split("T")[0];
  });
  const [slots, setSlots] = useState<SlotAvailability[]>([]);
  const [myBookings, setMyBookings] = useState<BookingItem[]>([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [bookingSlot, setBookingSlot] = useState<string | null>(null);
  const [activeBooking, setActiveBooking] = useState<BookingItem | null>(null);
  const [payOpen, setPayOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCourtsAndBookings = useCallback(async () => {
    try {
      const cList = await apiFetch<Court[]>("/api/v1/courts");
      setCourts(cList);
      if (cList.length > 0 && !selectedCourt) {
        setSelectedCourt(cList[0]);
      }
      if (user) {
        const mine = await apiFetch<BookingItem[]>("/api/v1/bookings/me");
        setMyBookings(mine);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load courts.");
    }
  }, [selectedCourt, user]);

  const loadAvailability = useCallback(async () => {
    if (!selectedCourt || !dateStr) return;
    setLoadingSlots(true);
    try {
      const avail = await apiFetch<SlotAvailability[]>(
        `/api/v1/courts/${selectedCourt.id}/availability?date=${dateStr}`
      );
      setSlots(avail);
    } catch (err: any) {
      setError(err.message || "Failed to load court availability.");
    } finally {
      setLoadingSlots(false);
    }
  }, [selectedCourt, dateStr]);

  useEffect(() => {
    loadCourtsAndBookings();
  }, [loadCourtsAndBookings]);

  useEffect(() => {
    loadAvailability();
  }, [loadAvailability]);

  const handleBookSlot = async (slot: SlotAvailability) => {
    if (!user || !selectedCourt) return;
    setBookingSlot(slot.slot_start);
    setError(null);
    try {
      const created = await apiFetch<BookingItem>("/api/v1/bookings", {
        method: "POST",
        body: JSON.stringify({
          court_id: selectedCourt.id,
          slot_start: slot.slot_start,
          slot_end: slot.slot_end,
        }),
      });
      setActiveBooking(created);
      setPayOpen(true);
      await loadAvailability();
      await loadCourtsAndBookings();
    } catch (err: any) {
      setError(err.message || "Could not lock slot (it may already be booked).");
      await loadAvailability();
    } finally {
      setBookingSlot(null);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold">
          Court & Turf Bookings
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Select a court, pick an hourly slot (protected by a 5-minute atomic Redis/in-memory lock), and complete checkout.
        </p>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-xs text-rose-300">
          {error}
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Court Selector */}
        <div className="space-y-3">
          <h2 className="font-bold text-sm text-slate-300 uppercase tracking-wider">
            1. Choose Facility Court
          </h2>
          {courts.map((c) => {
            const active = selectedCourt?.id === c.id;
            return (
              <button
                key={c.id}
                onClick={() => setSelectedCourt(c)}
                className={`w-full text-left p-4 rounded-2xl border transition ${
                  active
                    ? "bg-sky-500/15 border-sky-400 text-white"
                    : "bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-200"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 text-[10px] font-bold uppercase">
                    {c.sport_name}
                  </span>
                  <span className="font-bold text-sm text-emerald-400">
                    {formatINR(c.hourly_price)}/hr
                  </span>
                </div>
                <div className="font-bold text-sm mt-1">{c.name}</div>
                <div className="text-xs text-slate-400 flex items-center gap-1 mt-1">
                  <MapPin className="w-3 h-3" /> {c.venue}
                </div>
              </button>
            );
          })}
        </div>

        {/* Hourly Slot Grid */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-bold text-base">
                  2. Select Hourly Time Slot — {selectedCourt?.name}
                </h2>
                <p className="text-xs text-slate-400">
                  Clicking an available slot acquires an exclusive 5-minute lock (`SETNX`) while you pay.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-sky-400" />
                <input
                  type="date"
                  value={dateStr}
                  onChange={(e) => setDateStr(e.target.value)}
                  className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>
            </div>

            {!user && (
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-200 flex items-center justify-between">
                <span>Please sign in to reserve and pay for a court slot.</span>
                <Link
                  href="/login"
                  className="px-3 py-1 rounded-lg bg-amber-400 text-slate-950 font-bold"
                >
                  Sign In
                </Link>
              </div>
            )}

            {loadingSlots ? (
              <div className="py-12 flex justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-sky-400" />
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {slots.map((slot) => {
                  const isBusy = bookingSlot === slot.slot_start;
                  return (
                    <button
                      key={slot.slot_start}
                      disabled={!slot.available || !user || isBusy}
                      onClick={() => handleBookSlot(slot)}
                      className={`p-3 rounded-xl border text-left transition flex flex-col justify-between ${
                        slot.available
                          ? "bg-slate-950 hover:bg-sky-500/15 border-slate-800 hover:border-sky-400 cursor-pointer"
                          : slot.status === "LOCKED"
                          ? "bg-amber-500/10 border-amber-500/30 opacity-75 cursor-not-allowed"
                          : "bg-rose-500/10 border-rose-500/30 opacity-60 cursor-not-allowed"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs font-bold">
                        <span>{slot.label}</span>
                        {isBusy && <Loader2 className="w-3.5 h-3.5 animate-spin text-sky-400" />}
                      </div>

                      <div className="mt-2 flex items-center gap-1 text-[10px] font-semibold uppercase">
                        {slot.available ? (
                          <span className="text-emerald-400 flex items-center gap-1">
                            <Clock className="w-3 h-3" /> Available
                          </span>
                        ) : slot.status === "LOCKED" ? (
                          <span className="text-amber-300 flex items-center gap-1">
                            <Lock className="w-3 h-3" /> Locked (5m)
                          </span>
                        ) : (
                          <span className="text-rose-400 flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" /> Booked
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* My Bookings */}
          {user && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
              <h3 className="font-bold text-base">My Court Bookings ({myBookings.length})</h3>
              {myBookings.length === 0 ? (
                <p className="text-xs text-slate-400">No court bookings yet.</p>
              ) : (
                <div className="space-y-2">
                  {myBookings.map((b) => (
                    <div
                      key={b.id}
                      className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex flex-wrap items-center justify-between gap-3"
                    >
                      <div>
                        <div className="font-bold text-xs text-white">
                          {b.court_name || b.court_id}
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {new Date(b.slot_start).toLocaleString()} —{" "}
                          {new Date(b.slot_end).toLocaleTimeString()}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {b.payment_status === "CONFIRMED" ? (
                          <span className="px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-300 text-xs font-bold">
                            CONFIRMED
                          </span>
                        ) : (
                          <button
                            onClick={() => {
                              setActiveBooking(b);
                              setPayOpen(true);
                            }}
                            className="px-3 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs"
                          >
                            Complete Payment ({formatINR(b.hourly_price || 40000)})
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {activeBooking && (
        <PaymentModal
          open={payOpen}
          onClose={() => setPayOpen(false)}
          purpose="BOOKING"
          refId={activeBooking.id}
          title={`${activeBooking.court_name || selectedCourt?.name || "Court"} (${new Date(
            activeBooking.slot_start
          ).toLocaleString()})`}
          amountPaise={activeBooking.hourly_price || selectedCourt?.hourly_price || 40000}
          onSuccess={() => {
            setPayOpen(false);
            loadAvailability();
            loadCourtsAndBookings();
          }}
        />
      )}
    </div>
  );
}

