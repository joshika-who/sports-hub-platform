"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  Clock,
  FileCheck2,
  FileUp,
  Loader2,
  ShieldCheck,
  UserCog,
} from "lucide-react";
import { apiFetch, VaultDocument } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export default function VaultPage() {
  const { user, refreshUser, refreshNotifications } = useAuth();
  const [myDocs, setMyDocs] = useState<VaultDocument[]>([]);
  const [allDocs, setAllDocs] = useState<VaultDocument[]>([]);
  const [docType, setDocType] = useState<"ID" | "MEDICAL" | "WAIVER">("MEDICAL");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [age, setAge] = useState<number>(user?.profile_metrics?.age || 22);
  const [savingMetrics, setSavingMetrics] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    if (!user) return;
    try {
      const mine = await apiFetch<VaultDocument[]>("/api/v1/vault/documents");
      setMyDocs(mine);
      if (user.role === "organizer") {
        const everyone = await apiFetch<VaultDocument[]>(
          "/api/v1/vault/documents?all_users=true"
        );
        setAllDocs(everyone);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load documents.");
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      setAge(user.profile_metrics?.age || 22);
      loadDocuments();
    }
  }, [user, loadDocuments]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please choose a document file (PDF/PNG/JPG) to upload.");
      return;
    }
    setUploading(true);
    setError(null);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.append("doc_type", docType);
      formData.append("file", file);

      await apiFetch<VaultDocument>("/api/v1/vault/documents", {
        method: "POST",
        body: formData,
      });
      setMessage(
        `${docType} document uploaded! Status is Pending Verification until an Organizer approves it.`
      );
      setFile(null);
      await loadDocuments();
    } catch (err: any) {
      setError(err.message || "Document upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const handleVerify = async (docId: string) => {
    setVerifyingId(docId);
    setError(null);
    setMessage(null);
    try {
      await apiFetch<VaultDocument>(`/api/v1/vault/documents/${docId}/verify`, {
        method: "POST",
      });
      setMessage("Document verified and athlete notified!");
      await loadDocuments();
      await refreshNotifications();
    } catch (err: any) {
      setError(err.message || "Verification failed.");
    } finally {
      setVerifyingId(null);
    }
  };

  const handleUpdateAge = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingMetrics(true);
    setMessage(null);
    try {
      await apiFetch("/api/v1/auth/me/metrics", {
        method: "PUT",
        body: JSON.stringify({
          ...user?.profile_metrics,
          age: Number(age),
        }),
      });
      await refreshUser();
      setMessage("Athlete profile metrics updated.");
    } catch (err: any) {
      setError(err.message || "Failed to update metrics.");
    } finally {
      setSavingMetrics(false);
    }
  };

  if (!user) {
    return (
      <div className="p-8 rounded-2xl bg-slate-900 border border-slate-800 text-center space-y-4">
        <FileCheck2 className="w-10 h-10 text-sky-400 mx-auto" />
        <h2 className="text-lg font-bold">Sign in to access your Document Vault</h2>
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
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold">Verified Document Vault</h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Upload your Government ID, Medical Certificate, and Liability Waiver once for instant tournament eligibility.
        </p>
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

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Upload Form + Metrics */}
        <div className="space-y-6">
          <form
            onSubmit={handleUpload}
            className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4"
          >
            <div className="flex items-center gap-2 font-bold text-sm text-sky-400">
              <FileUp className="w-4 h-4" /> Upload New Document
            </div>

            <div>
              <label className="block text-xs text-slate-300 mb-1.5">Document Type</label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value as any)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
              >
                <option value="ID">ID (Government / Federation ID)</option>
                <option value="MEDICAL">MEDICAL (Sports Fitness Certificate)</option>
                <option value="WAIVER">WAIVER (Signed Liability Waiver)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs text-slate-300 mb-1.5">Select File</label>
              <input
                type="file"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="w-full text-xs text-slate-300 file:mr-3 file:py-2 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-sky-500/20 file:text-sky-300 hover:file:bg-sky-500/30"
              />
            </div>

            <button
              type="submit"
              disabled={uploading}
              className="w-full py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 transition"
            >
              {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              Upload to Vault
            </button>
          </form>

          <form
            onSubmit={handleUpdateAge}
            className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3"
          >
            <div className="flex items-center gap-2 font-bold text-sm text-slate-200">
              <UserCog className="w-4 h-4 text-sky-400" /> Athlete Age & Metrics
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <label className="block text-[11px] text-slate-400 mb-1">Profile Age</label>
                <input
                  type="number"
                  min={8}
                  max={90}
                  value={age}
                  onChange={(e) => setAge(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
                />
              </div>
              <button
                type="submit"
                disabled={savingMetrics}
                className="mt-5 px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold text-white"
              >
                {savingMetrics ? "Saving..." : "Update Age"}
              </button>
            </div>
          </form>
        </div>

        {/* My Vault List */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
            <h2 className="font-bold text-base">My Vault Documents ({myDocs.length})</h2>

            {myDocs.length === 0 ? (
              <p className="text-xs text-slate-400 py-6 text-center">
                No documents uploaded yet. Upload your ID, MEDICAL, or WAIVER document on the left.
              </p>
            ) : (
              <div className="space-y-2.5">
                {myDocs.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex flex-wrap items-center justify-between gap-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono text-xs font-bold">
                          {doc.doc_type}
                        </span>
                        <span className="text-xs text-slate-400 font-mono">
                          {doc.storage_url}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Uploaded {new Date(doc.uploaded_at).toLocaleString()}
                      </div>
                    </div>

                    {doc.is_verified ? (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-xs font-bold">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Verified
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 text-xs font-bold">
                        <Clock className="w-3.5 h-3.5" /> Pending Organizer Verification
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Organizer Verification Console */}
          {user.role === "organizer" && (
            <div className="bg-slate-900 border border-sky-500/30 rounded-2xl p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-sky-400" />
                  <h2 className="font-bold text-base">
                    Organizer Document Verification Queue ({allDocs.length})
                  </h2>
                </div>
                <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-sky-500/20 text-sky-300 font-bold">
                  ORGANIZER PRIVILEGE
                </span>
              </div>

              <div className="space-y-2.5">
                {allDocs.map((doc) => (
                  <div
                    key={doc.id}
                    className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex flex-wrap items-center justify-between gap-3"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono text-xs font-bold">
                          {doc.doc_type}
                        </span>
                        <span className="text-xs font-semibold text-white">
                          {doc.user_name || doc.user_email || doc.user_id}
                        </span>
                        <span className="text-xs text-slate-400">({doc.user_email})</span>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5 font-mono">
                        Ref: {doc.storage_url}
                      </div>
                    </div>

                    {doc.is_verified ? (
                      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-emerald-500/15 text-emerald-300 text-xs font-bold">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Verified
                      </span>
                    ) : (
                      <button
                        onClick={() => handleVerify(doc.id)}
                        disabled={verifyingId === doc.id}
                        className="px-4 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition"
                      >
                        {verifyingId === doc.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        )}
                        Verify Document
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

