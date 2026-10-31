"use client";

import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Cpu,
  Loader2,
  Send,
  ShieldPlus,
  Sparkles,
} from "lucide-react";
import { API_BASE_URL, apiFetch } from "@/lib/api";

interface RagSource {
  id: string;
  source: string;
  title: string;
}

interface InjuryHealth {
  status: string;
  ollama_url: string;
  ollama_model: string;
  ollama_reachable: boolean;
  chromadb_reachable: boolean;
  indexed_chunks: number;
  fallback_mode: string;
}

const SAMPLE_PROMPTS = [
  {
    label: "Lateral Ankle Sprain",
    sport: "Badminton",
    q: "I rolled my ankle landing from an overhead smash. How do I use PEACE & LOVE and when do I need an X-ray under the Ottawa Ankle Rules?",
  },
  {
    label: "ACL Injury Prevention",
    sport: "Football",
    q: "What neuromuscular warm-up and landing mechanics prevent non-contact ACL tears in football?",
  },
  {
    label: "Tennis Elbow Rehab",
    sport: "Tennis",
    q: "My outer elbow aches during backhand strokes. What isometric and eccentric exercises help lateral epicondylalgia?",
  },
  {
    label: "Concussion Red Flags",
    sport: "Basketball",
    q: "A player collided heads and feels dizzy and sensitive to light. What are the emergency red flags and graduated return-to-play stages?",
  },
];

export default function InjuryCarePage() {
  const [question, setQuestion] = useState(SAMPLE_PROMPTS[0].q);
  const [sport, setSport] = useState(SAMPLE_PROMPTS[0].sport);
  const [history, setHistory] = useState("Mild swelling on lateral malleolus, able to walk 4 steps");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<RagSource[]>([]);
  const [mode, setMode] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [health, setHealth] = useState<InjuryHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<InjuryHealth>("/api/v1/injury/health")
      .then(setHealth)
      .catch(() => {});
  }, []);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setStreaming(true);
    setAnswer("");
    setSources([]);
    setMode(null);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/injury/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          sport,
          history,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const parsed = JSON.parse(line);
            if (parsed.token) {
              setAnswer((prev) => prev + parsed.token);
            }
            if (parsed.done) {
              setSources(parsed.sources || []);
              setMode(parsed.mode || "retrieval_only");
            }
          } catch {
            // ignore partial line
          }
        }
      }
    } catch (err: any) {
      setError(err.message || "Failed to stream response from Injury AI.");
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold flex items-center gap-2.5">
            <ShieldPlus className="w-7 h-7 text-sky-400" />
            AI Sports Injury-Prevention & Recovery Assistant
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Powered by ChromaDB RAG over 11 clinical sports-medicine protocols + Ollama (`{health?.ollama_model || "gemma3:1b"}`) with automatic retrieval fallback.
          </p>
        </div>

        {health && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-emerald-400 font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5" />
              RAG Corpus: {health.indexed_chunks} chunks
            </span>
            <span className="text-slate-600">|</span>
            <span className="flex items-center gap-1.5 text-sky-300 font-mono">
              <Cpu className="w-3.5 h-3.5" />
              {health.ollama_reachable
                ? `Ollama Live (${health.ollama_model})`
                : `Fallback Ready (${health.ollama_model})`}
            </span>
          </div>
        )}
      </div>

      {/* Quick Prompts */}
      <div className="flex flex-wrap gap-2">
        {SAMPLE_PROMPTS.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => {
              setSport(item.sport);
              setQuestion(item.q);
            }}
            className="px-3 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-sky-300 font-medium flex items-center gap-1.5 transition"
          >
            <Sparkles className="w-3.5 h-3.5" />
            {item.label}
          </button>
        ))}
      </div>

      <div className="grid lg:grid-cols-12 gap-6">
        <form
          onSubmit={handleAsk}
          className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 h-fit"
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-300 mb-1">Sport</label>
              <select
                value={sport}
                onChange={(e) => setSport(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
              >
                <option value="Badminton">Badminton</option>
                <option value="Football">Football</option>
                <option value="Tennis">Tennis</option>
                <option value="Basketball">Basketball</option>
                <option value="Running">Running / Athletics</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-300 mb-1">Context / History</label>
              <input
                type="text"
                value={history}
                onChange={(e) => setHistory(e.target.value)}
                placeholder="Optional injury history..."
                className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs text-slate-300 mb-1">
              Symptom or Prevention Question
            </label>
            <textarea
              rows={4}
              required
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-sky-500"
            />
          </div>

          <button
            type="submit"
            disabled={streaming}
            className="w-full py-3 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center justify-center gap-2 transition"
          >
            {streaming ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Streaming RAG Guidance...
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                Ask Injury Prevention AI
              </>
            )}
          </button>

          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-200/90 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <span>
              <strong>Safety Notice:</strong> Educational sports-physiotherapy guidance only — not a medical diagnosis. Always consult a physician for severe pain, fractures, or concussion red flags.
            </span>
          </div>
        </form>

        {/* Streamed Answer & RAG Sources */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5 flex flex-col justify-between min-h-[360px]">
          {error ? (
            <div className="p-4 rounded-xl bg-rose-500/15 border border-rose-500/30 text-xs text-rose-300">
              {error}
            </div>
          ) : !answer && !streaming ? (
            <div className="my-auto text-center space-y-2 text-slate-400 py-12">
              <ShieldPlus className="w-10 h-10 text-slate-600 mx-auto" />
              <div className="font-semibold text-sm text-slate-300">
                Ask any sports injury or recovery question
              </div>
              <p className="text-xs max-w-md mx-auto">
                Click &ldquo;Ask Injury Prevention AI&rdquo; to retrieve the top 4 ChromaDB clinical chunks and stream the response in real time.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {mode && (
                <div className="flex items-center justify-between text-xs border-b border-slate-800 pb-2.5">
                  <span className="font-bold text-sky-400">
                    Evidence-Based Guidance Stream
                  </span>
                  <span className="px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono text-[11px]">
                    Engine: {mode === "ollama_rag" ? "Ollama LLM + ChromaDB RAG" : "ChromaDB Retrieval-Only Fallback"}
                  </span>
                </div>
              )}

              <div className="prose prose-invert max-w-none text-xs sm:text-sm leading-relaxed whitespace-pre-wrap text-slate-200">
                {answer}
                {streaming && (
                  <span className="inline-block w-2 h-4 ml-1 bg-sky-400 animate-pulse align-middle" />
                )}
              </div>
            </div>
          )}

          {sources.length > 0 && (
            <div className="pt-4 border-t border-slate-800">
              <div className="text-xs font-bold text-slate-300 flex items-center gap-1.5 mb-2.5">
                <BookOpen className="w-3.5 h-3.5 text-sky-400" />
                Retrieved ChromaDB Corpus Sources ({sources.length}):
              </div>
              <div className="grid sm:grid-cols-2 gap-2">
                {sources.map((src) => (
                  <div
                    key={src.id}
                    className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs"
                  >
                    <div className="font-semibold text-sky-300 truncate">{src.title}</div>
                    <div className="font-mono text-[10px] text-slate-500">{src.source}</div>
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

