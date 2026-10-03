"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const STEPS = [["/capture", "Capture"], ["/debrief", "Debrief"], ["/map", "Work Map"], ["/teach", "Teach"]];

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
      </div>
    </header>
  );
}

export function SafetyFooter() {
  return (
    <footer className="mt-auto border-t border-line bg-sage px-4 py-2 text-center text-sm">
      Training and documentation support only. Not diagnosis or treatment. Pain, medication, or deterioration concerns must escalate to a clinician. Demo uses fake data.
    </footer>
  );
}
