"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { KeyRound, Loader2, Shield, Sparkles, UserCheck } from "lucide-react";
import { apiFetch, TokenResponse } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const DEMO_ACCOUNTS = [
  {
    label: "Athlete 1 (Verified ID only)",
    email: "athlete@demo.com",
    role: "athlete",
    desc: "Age 22 • Needs MEDICAL doc for Championship",
  },
  {
    label: "Athlete 2 (All Docs Verified)",
    email: "athlete2@demo.com",
    role: "athlete",
    desc: "Age 24 • Eligible for 1-click registration",
  },
  {
    label: "Organizer Account",
    email: "organizer@demo.com",
    role: "organizer",
    desc: "Verify Vault docs, create events & run AI Scheduler",
  },
  {
    label: "Referee Account",
    email: "referee@demo.com",
    role: "referee",
    desc: "Push real-time live score updates over WebSocket",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const { setSession } = useAuth();
  const [email, setEmail] = useState("athlete@demo.com");
  const [password, setPassword] = useState("Passw0rd!");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setSession(resp);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Login failed. Check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const quickLogin = async (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword("Passw0rd!");
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: demoEmail, password: "Passw0rd!" }),
      });
      setSession(resp);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Quick login failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto grid md:grid-cols-2 gap-8 items-start py-6">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <KeyRound className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Sign In to Sports Hub</h1>
            <p className="text-xs text-slate-400">
              Access your Document Vault, Bookings & Tournaments
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-xs text-rose-300">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-sky-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-sky-500"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold text-sm flex items-center justify-center gap-2 transition"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Sign In
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-slate-400">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-sky-400 hover:underline font-medium">
            Create an Athlete or Organizer account
          </Link>
        </p>
      </div>

      <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-2 text-sky-400 font-semibold text-sm">
          <Sparkles className="w-4 h-4" />
          One-Click Demo Accounts (Password: <code className="text-white">Passw0rd!</code>)
        </div>
        <p className="text-xs text-slate-400">
          Click any seeded account below to sign in immediately and test role-specific flows:
        </p>

        <div className="space-y-2.5">
          {DEMO_ACCOUNTS.map((acc) => (
            <button
              key={acc.email}
              type="button"
              onClick={() => quickLogin(acc.email)}
              className="w-full text-left p-3.5 rounded-xl bg-slate-950/80 hover:bg-slate-800/80 border border-slate-800 hover:border-sky-500/40 transition group"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-sm text-slate-100 group-hover:text-sky-300 flex items-center gap-1.5">
                  <UserCheck className="w-4 h-4 text-sky-400" />
                  {acc.label}
                </span>
                <span className="uppercase text-[10px] font-bold px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-300">
                  {acc.role}
                </span>
              </div>
              <div className="text-xs text-slate-400">{acc.email} — {acc.desc}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

