"use client";

import React, { useState } from "react";
import { CheckCircle2, CreditCard, Loader2, ShieldCheck, X } from "lucide-react";
import { apiFetch, formatINR, PaymentIntentResponse } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

interface PaymentModalProps {
  open: boolean;
  onClose: () => void;
  purpose: "REGISTRATION" | "BOOKING";
  refId: string;
  title: string;
  amountPaise: number;
  onSuccess: () => void;
}

export default function PaymentModal({
  open,
  onClose,
  purpose,
  refId,
  title,
  amountPaise,
  onSuccess,
}: PaymentModalProps) {
  const { refreshNotifications } = useAuth();
  const [gateway, setGateway] = useState<"stripe" | "razorpay" | "phonepe">("stripe");
  const [intent, setIntent] = useState<PaymentIntentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  if (!open) return null;

  const handleCreateIntent = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<PaymentIntentResponse>("/api/v1/payments/create-intent", {
        method: "POST",
        body: JSON.stringify({
          purpose,
          ref_id: refId,
          gateway,
        }),
      });
      setIntent(res);
    } catch (err: any) {
      setError(err.message || "Failed to initialize payment intent.");
    } finally {
      setLoading(false);
    }
  };

  const handleSimulateComplete = async () => {
    if (!intent) return;
    setCompleting(true);
    setError(null);
    try {
      await apiFetch(`/api/v1/payments/mock/complete/${intent.payment_id}`, {
        method: "POST",
      });
      setDone(true);
      await refreshNotifications();
      setTimeout(() => {
        onSuccess();
      }, 900);
    } catch (err: any) {
      setError(err.message || "Payment verification failed.");
    } finally {
      setCompleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl text-white relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <CreditCard className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-lg">Unified Sports Checkout</h3>
            <p className="text-xs text-slate-400">{purpose} PAYMENT</p>
          </div>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 mb-5">
          <div className="text-xs text-slate-400 mb-1">Item</div>
          <div className="font-medium text-sm text-slate-100 mb-2">{title}</div>
          <div className="flex items-baseline justify-between border-t border-slate-800 pt-2">
            <span className="text-xs text-slate-400">Total Payable</span>
            <span className="text-xl font-bold text-emerald-400">{formatINR(amountPaise)}</span>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-xs text-rose-300">
            {error}
          </div>
        )}

        {done ? (
          <div className="py-6 text-center space-y-2">
            <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto animate-bounce" />
            <div className="font-bold text-lg text-emerald-300">Payment Confirmed!</div>
            <p className="text-xs text-slate-400">
              Webhook processed & push notification dispatched.
            </p>
          </div>
        ) : !intent ? (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-2">
                Select Payment Gateway Adapter
              </label>
              <div className="grid grid-cols-3 gap-2">
                {(["stripe", "razorpay", "phonepe"] as const).map((gw) => (
                  <button
                    key={gw}
                    type="button"
                    onClick={() => setGateway(gw)}
                    className={`py-2.5 px-3 rounded-xl border text-xs font-semibold uppercase tracking-wider transition ${
                      gateway === gw
                        ? "bg-sky-500/20 border-sky-400 text-sky-300"
                        : "bg-slate-800/60 border-slate-700 text-slate-400 hover:text-white"
                    }`}
                  >
                    {gw}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={handleCreateIntent}
              disabled={loading}
              className="w-full py-3 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold text-sm flex items-center justify-center gap-2 transition"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              Create Payment Order ({gateway.toUpperCase()})
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="p-3.5 rounded-xl bg-slate-800/70 border border-slate-700 text-xs space-y-1.5">
              <div className="flex justify-between">
                <span className="text-slate-400">Gateway:</span>
                <span className="font-semibold uppercase text-sky-300">{intent.gateway}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Order ID:</span>
                <span className="font-mono text-slate-200">{intent.order_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Mode:</span>
                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold uppercase text-[10px]">
                  {intent.mode}
                </span>
              </div>
            </div>

            <button
              onClick={handleSimulateComplete}
              disabled={completing}
              className="w-full py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold text-sm flex items-center justify-center gap-2 transition shadow-lg shadow-emerald-500/20"
            >
              {completing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ShieldCheck className="w-4 h-4" />
              )}
              Simulate Successful Payment
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

