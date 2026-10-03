"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/engine";

const STEPS = [["/capture", "Capture"], ["/debrief", "Debrief"], ["/map", "Work Map"], ["/teach", "Teach"]];

function EngineBadge() {
  const [h, setH] = useState<{ degraded: boolean; usage: { calls: number; est_usd: number } } | null | "down">(null);
  useEffect(() => {
    const tick = () => api.health().then(setH).catch(() => setH("down"));
    tick(); const t = setInterval(tick, 5000); return () => clearInterval(t);
  }, []);
  if (h === "down") return <span className="chip border-coral text-coral">Engine offline</span>;
  if (!h) return null;
  return <span className={`chip ${h.degraded ? "border-amber bg-amber/20" : ""}`} title="Estimated API spend this machine; the provider balance is not exposed.">
    {h.degraded ? "Degraded mode: cached/offline logic in use" : "Live"} · {h.usage.calls} LLM calls · ~${h.usage.est_usd.toFixed(3)}</span>;
}

export function Nav() {
  const p = usePathname();
  return (
    <header className="border-b border-line bg-white">
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
        <span className="text-xl font-bold text-teal">Apprentice</span>
        <nav className="flex gap-2">
          {STEPS.map(([href, label], i) => (
            <Link key={href} href={href} className={`chip ${p === href ? "bg-teal text-white" : ""}`}>{i + 1}. {label}</Link>))}
        </nav>
        <span className="ml-auto"><EngineBadge /></span>
      </div>
    </header>
  );
}

export function SafetyFooter() {
  return (
    <footer className="mt-auto border-t border-line bg-sage px-4 py-2 text-center text-sm">
      Training and documentation support only. Not diagnosis or treatment. Pain, medication, or deterioration concerns must escalate to a clinician. Demo uses fake data.{" "}
      <Link href="/moonshot" className="underline">Moonshot slide</Link>
    </footer>
  );
}
