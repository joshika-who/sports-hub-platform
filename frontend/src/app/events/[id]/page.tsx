"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Calendar,
  CheckCircle2,
  FileUp,
  Loader2,
  MapPin,
  ShieldCheck,
  Users,
  XCircle,
} from "lucide-react";
import {
  apiFetch,
  EligibilityResponse,
  formatINR,
  RegistrationItem,
  SportEvent,
} from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import PaymentModal from "@/components/PaymentModal";

export default function EventDetailPage() {
  const params = useParams();
  const eventId = String(params.id || "");
  const { user, refreshNotifications } = useAuth();

  const [event, setEvent] = useState<SportEvent | null>(null);
  const [eligibility, setEligibility] = useState<EligibilityResponse | null>(null);
  const [registration, setRegistration] = useState<RegistrationItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payOpen, setPayOpen] = useState(false);

  const loadDetails = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const ev = await apiFetch<SportEvent>(`/api/v1/events/${eventId}`);
      setEvent(ev);

      if (user) {
        const [elig, myRegs] = await Promise.all([
          apiFetch<EligibilityResponse>(`/api/v1/events/${eventId}/eligibility`),
          apiFetch<RegistrationItem[]>("/api/v1/events/registrations/me"),
        ]);
        setEligibility(elig);
        const found = myRegs.find((r) => r.event_id === eventId);
        setRegistration(found || null);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load event details.");
    } finally {
      setLoading(false);
    }
  }, [eventId, user]);

  useEffect(() => {
    if (eventId) loadDetails();
  }, [eventId, loadDetails]);

  const handleOneClickRegister = async () => {
    setRegistering(true);
    setError(null);
    try {
      const reg = await apiFetch<RegistrationItem>(`/api/v1/events/${eventId}/register`, {
        method: "POST",
      });
      setRegistration(reg);
      if (reg.status === "PENDING_PAYMENT") {
        setPayOpen(true);
      } else {
        await refreshNotifications();
        await loadDetails();
      }
    } catch (err: any) {
      setError(err.message || "Registration blocked by eligibility engine.");
      if (err.checks) {
        setEligibility({ eligible: false, checks: err.checks });
      }
    } finally {
      setRegistering(false);
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex flex-col items-center justify-center gap-3 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
        <p className="text-sm">Evaluating event & athlete eligibility...</p>
      </div>
    );
  }

  if (!event) {
    return (
      <div className="p-6 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300">
        {error || "Event not found."}
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-white"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Event Discovery
      </Link>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <span className="px-3 py-1 rounded-lg bg-sky-500/15 text-sky-300 text-xs font-bold uppercase tracking-wider">
              {event.sport_name}
            </span>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white">{event.title}</h1>
          </div>

          <div className="bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-right">
            <div className="text-[11px] uppercase text-slate-400 font-semibold">Entry Fee</div>
            <div className="text-2xl font-black text-emerald-400">
              {formatINR(event.entry_fee)}
            </div>
          </div>
        </div>

        <div className="grid sm:grid-cols-3 gap-4 pt-2 border-t border-slate-800 text-xs text-slate-300">
          <div className="flex items-center gap-2.5 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
            <MapPin className="w-4 h-4 text-sky-400 shrink-0" />
            <span>{event.venue}</span>
          </div>
          <div className="flex items-center gap-2.5 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
            <Calendar className="w-4 h-4 text-sky-400 shrink-0" />
            <span>{new Date(event.date_time).toLocaleString()}</span>
          </div>
          <div className="flex items-center gap-2.5 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
            <Users className="w-4 h-4 text-sky-400 shrink-0" />
            <span>
              {event.registered_count} / {event.capacity} Spots Filled
            </span>
          </div>
        </div>

        {/* Eligibility Engine Checklist */}
        <div className="bg-slate-950 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-sky-400" />
              <h2 className="font-bold text-base">Automated Eligibility Verification</h2>
            </div>

            {eligibility && (
              <span
                className={`px-3 py-1 rounded-full text-xs font-bold ${
                  eligibility.eligible
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                }`}
              >
                {eligibility.eligible ? "ALL CHECKS PASSED" : "MISSING REQUIREMENTS"}
              </span>
            )}
          </div>

          {!user ? (
            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
              <span className="text-xs text-slate-300">
                Sign in to verify your age and Document Vault eligibility for this event.
              </span>
              <Link
                href="/login"
                className="px-4 py-2 rounded-xl bg-sky-500 text-slate-950 font-bold text-xs"
              >
                Sign In
              </Link>
            </div>
          ) : eligibility ? (
            <div className="space-y-2.5">
              {eligibility.checks.map((chk) => (
                <div
                  key={chk.requirement}
                  className={`p-3.5 rounded-xl border flex items-start justify-between gap-3 ${
                    chk.passed
                      ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-200"
                      : "bg-rose-500/10 border-rose-500/30 text-rose-200"
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    {chk.passed ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    ) : (
                      <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                    )}
                    <div>
                      <div className="font-mono text-xs font-bold">{chk.requirement}</div>
                      <div className="text-xs opacity-90 mt-0.5">{chk.message}</div>
                    </div>
                  </div>

                  {!chk.passed && !chk.requirement.startsWith("MIN_AGE") && (
                    <Link
                      href="/vault"
                      className="shrink-0 inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-rose-500 hover:bg-rose-400 text-slate-950 font-bold text-xs transition"
                    >
                      <FileUp className="w-3.5 h-3.5" /> Go to Vault
                    </Link>
                  )}
                </div>
              ))}
            </div>
          ) : null}
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-xs text-rose-300">
            {error}
          </div>
        )}

        {/* Registration Action Footer */}
        {user && (
          <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
            {registration?.status === "CONFIRMED" ? (
              <div className="w-full p-4 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-between">
                <div className="flex items-center gap-2.5 text-emerald-300 font-bold text-sm">
                  <CheckCircle2 className="w-5 h-5" />
                  You are officially REGISTERED & CONFIRMED for this tournament!
                </div>
                <span className="text-xs font-mono text-emerald-400">
                  ID: {registration.id.slice(0, 8)}
                </span>
              </div>
            ) : registration?.status === "PENDING_PAYMENT" ? (
              <div className="w-full p-4 rounded-xl bg-amber-500/15 border border-amber-500/30 flex flex-wrap items-center justify-between gap-3">
                <div className="text-xs text-amber-200">
                  <span className="font-bold">Registration Reserved (Pending Payment):</span>{" "}
                  Complete your entry fee payment to confirm your spot.
                </div>
                <button
                  onClick={() => setPayOpen(true)}
                  className="px-5 py-2.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs transition"
                >
                  Pay {formatINR(event.entry_fee)} Now
                </button>
              </div>
            ) : (
              <button
                onClick={handleOneClickRegister}
                disabled={registering || (eligibility !== null && !eligibility.eligible)}
                className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-40 disabled:cursor-not-allowed text-slate-950 font-extrabold text-sm flex items-center justify-center gap-2 transition shadow-lg shadow-sky-500/20"
              >
                {registering ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {eligibility && !eligibility.eligible
                  ? "Complete Missing Vault Requirements to Register"
                  : `One-Click Register (${formatINR(event.entry_fee)})`}
              </button>
            )}
          </div>
        )}
      </div>

      {registration && (
        <PaymentModal
          open={payOpen}
          onClose={() => setPayOpen(false)}
          purpose="REGISTRATION"
          refId={registration.id}
          title={event.title}
          amountPaise={event.entry_fee}
          onSuccess={() => {
            setPayOpen(false);
            loadDetails();
          }}
        />
      )}
    </div>
  );
}

