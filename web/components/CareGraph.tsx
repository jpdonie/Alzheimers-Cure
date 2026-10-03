"use client";
import { forceCollide, forceLink, forceManyBody, forceRadial, forceSimulation, type Simulation, type SimulationLinkDatum, type SimulationNodeDatum } from "d3-force";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, explain, type CareGraphData, type GraphEdge, type GraphNode } from "@/lib/engine";

type N = GraphNode & SimulationNodeDatum;
type L = SimulationLinkDatum<N> & GraphEdge;

const RING: Record<string, number> = { rule: 0, field: 215, guardrail: 175, exception: 175, route: 255, moment: 140, guideline: 300, unit: 335, related: 365, learned: 405 };
const KIND_COLOR: Record<string, string> = { decision_rule: "#0f4c5c", escalation_rule: "#d9544d", principle: "#8aa39d", process: "#c9b79c", measurement: "#7b8fb5", other: "#bbb" };
const EDGE_COLOR: Record<string, string> = { tests: "#9aa7a4", guardrail: "#e8a33d", exception: "#8aa39d", routes_to: "#d9544d", then: "#d9544d", cites: "#0f4c5c", learned_from: "#d8d2c6", re_derives: "#0f4c5c", related: "#c9b79c", seen_live: "#0f4c5c", context: "#7b8fb5" };
const LEGEND: [string, string][] = [["rule", "Rule"], ["guardrail", "Guardrail"], ["route", "Hand-over route"], ["field", "Form field it tests"], ["moment", "Live screen moment"], ["unit", "Interview unit (cited)"], ["related", "Related unit (retrieved)"], ["guideline", "Guideline context"], ["learned", "Learned card (all interviews)"]];
const trunc = (t: string, n: number) => (t.length > n ? t.slice(0, n - 1) + "…" : t);
const id = (v: string | N) => (typeof v === "string" ? v : v.id);

function shape(n: N, hot: boolean) {
  const x = n.x ?? 0, y = n.y ?? 0, op = hot ? 1 : 0.18;
  const common = { opacity: op, style: { cursor: "pointer" } as const };
  switch (n.type) {
    case "rule": {
      const w = 178 + (n.risk ?? 1) * 6, h = 42, st = n.status;
      const fill = st === "confirmed" ? "#0f4c5c" : st === "live" ? "#dce8e2" : st === "rejected" ? "#fbe3e1" : "#fff";
      const stroke = st === "rejected" ? "#d9544d" : "#0f4c5c";
      return <g {...common}><rect x={x - w / 2} y={y - h / 2} width={w} height={h} rx={10} fill={fill} stroke={stroke} strokeWidth={2} strokeDasharray={st === "hypothesis" ? "5 3" : undefined} />
        <text x={x} y={y - 3} textAnchor="middle" fontSize={11.5} fontWeight={700} fill={st === "confirmed" ? "#fff" : "#1b2a2f"}>{trunc(n.label, 27)}</text>
        <text x={x} y={y + 12} textAnchor="middle" fontSize={9.5} fill={st === "confirmed" ? "#dce8e2" : "#55666a"}>{String(n.detail.severity) === "block" ? "blocks Save" : "warns"} · {st}{n.learned ? " · learned" : ""}</text></g>;
    }
    case "guardrail": return <g {...common}><rect x={x - 72} y={y - 14} width={144} height={28} rx={14} fill="#fdf0d8" stroke="#e8a33d" strokeDasharray={n.status === "hypothesized" ? "4 3" : undefined} /><text x={x} y={y + 4} textAnchor="middle" fontSize={10}>{trunc(n.label, 27)}</text></g>;
    case "exception": return <g {...common}><rect x={x - 60} y={y - 11} width={120} height={22} rx={11} fill="#dce8e2" stroke="#8aa39d" /><text x={x} y={y + 3} textAnchor="middle" fontSize={8.5}>{trunc(n.label, 26)}</text></g>;
    case "route": return <g {...common}><circle cx={x} cy={y} r={26} fill="#fbe3e1" stroke="#d9544d" strokeWidth={2} /><text x={x} y={y + 4} textAnchor="middle" fontSize={9.5} fontWeight={700}>{trunc(n.label, 11)}</text></g>;
    case "field": return <g {...common}><rect x={x - 46} y={y - 11} width={92} height={22} rx={5} fill="#eef0ef" stroke="#9aa7a4" /><text x={x} y={y + 4} textAnchor="middle" fontSize={10}>{trunc(n.label, 17)}</text></g>;
    case "moment": return <g {...common}><circle cx={x} cy={y} r={14} fill="#0f4c5c" /><text x={x} y={y + 3.5} textAnchor="middle" fontSize={9} fill="#fff">live</text></g>;
    case "guideline": return <g {...common}><path d={`M${x},${y - 11} L${x + 11},${y} L${x},${y + 11} L${x - 11},${y} Z`} fill="#e6ebf5" stroke="#7b8fb5" /><text x={x} y={y + 3} textAnchor="middle" fontSize={7}>{String(n.detail.page)}</text></g>;
    case "unit": case "related": return <g {...common}><circle cx={x} cy={y} r={n.type === "unit" ? 8 : 7} fill={n.type === "unit" ? "#dce8e2" : "#fff"} stroke="#0f4c5c" strokeDasharray={n.type === "related" ? "2 2" : undefined} /></g>;
    default: {      // learned card
      const r = n.safety ? 7 : 6, ring = n.status === "accepted" ? "#0f4c5c" : n.status === "rejected" ? "#d9544d" : n.safety ? "#d9544d" : "#ffffff";
      return <g {...common}><circle cx={x} cy={y} r={r} fill={KIND_COLOR[n.kind ?? "other"]} stroke={ring} strokeWidth={n.status === "accepted" ? 2.5 : 1.2} /></g>;
    }
  }
}

function Panel({ n, g, onReview }: { n: GraphNode | null; g: CareGraphData; onReview: (id: string, d: "confirm" | "reject" | "reset") => void }) {
  if (!n) return <div className="card text-sm"><b>Click any node.</b> Rules sit in the middle, tested form fields, guardrails and hand-over routes around them, then the interview evidence, and on the outer ring every card the apprentice learned from all the interviews. Teal lines marked “re-derives” show where the learner independently rediscovered a curated rule.</div>;
  const d = n.detail as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  const nbr = g.edges.filter((e) => e.source === n.id || e.target === n.id);
  const list = (xs?: string[]) => (xs && xs.length ? <ul className="list-disc pl-5">{xs.map((x) => <li key={x}>{x}</li>)}</ul> : <span className="text-coral">none stated</span>);
  return (
    <div className="card space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2"><span className="chip">{n.type}</span>{n.status && <span className="chip">{n.status}</span>}<b>{String(d.title ?? d.text ?? n.label)}</b></div>
      {n.type === "rule" && (<>
        <p><b>Context:</b> {d.context}</p><p><b>Action:</b> {d.action}</p><p><b>Why:</b> {d.rationale}</p>{d.escalation && <p><b>Hand over to:</b> {d.escalation}</p>}
        <p className="font-mono text-xs">{d.severity === "block" ? "blocks Save when" : "warns when"}: {d.predicate}</p>
        <p className="text-xs">Confidence: {d.confidence} · {d.evidence_strength} · risk {d.risk}/3 {d.reviewed && `· ${d.reviewed} by expert review`}</p>
        <div className="rounded border border-line bg-paper p-2 text-xs"><b>CBT checklist:</b> formulation {d.cbt.formulation ? "✓" : "○"} · targeted intervention {d.cbt.targeted_intervention ? "✓" : "○"} · measurement {d.cbt.measurement ? "✓" : "○ not recorded"} · empirical validation {d.cbt.empirical_validation ? "✓" : "○ not supplied"}
          <p className="mt-1">{d.cbt.safeguards.delivery_not_effectiveness}</p><p>{d.cbt.safeguards.evidence_does_not_transfer}</p></div>
        {d.caution && <p className="text-xs text-ink/70">Caveat: {d.caution}</p>}
        <div className="flex flex-wrap gap-2"><button className="btn btn-primary" onClick={() => onReview(d.rule_id, "confirm")}>Confirm</button><button className="btn btn-ghost" onClick={() => onReview(d.rule_id, "reject")}>Reject</button>{d.reviewed && <button className="btn btn-ghost" onClick={() => onReview(d.rule_id, "reset")}>Undo</button>}</div></>)}
      {n.type === "learned" && (<>
        <p><b>Context:</b> {d.context || "not stated"}</p><p><b>Action:</b> {d.action || "not stated"}</p><p><b>Why:</b> {d.rationale || "not stated"}</p>
        <div><b>Guardrails:</b>{list(d.guardrails)}</div><div><b>Exceptions:</b>{list(d.exceptions)}</div><div><b>Escalation:</b>{list(d.escalation)}</div>
        {d.predicate && <p className="font-mono text-xs">proposed check: {d.predicate}</p>}
        {(d.evidence ?? []).map((e: { span: string; unit_id: string; turn_id: string }, i: number) => <blockquote key={i} className="quote">“{e.span}” <span className="text-xs">({e.unit_id}, {e.turn_id}, verbatim, code-checked)</span></blockquote>)}
        <p className="text-xs">{d.kind} · sessions {d.sessions?.join(", ")} · {d.corroboration >= 2 ? `${d.corroboration} sessions agree` : "single session"}{d.safety_critical ? " · safety-critical" : ""}</p>
        <div className="flex flex-wrap gap-2"><button className="btn btn-primary" onClick={() => onReview(d.card_id, "confirm")}>Accept</button><button className="btn btn-ghost" onClick={() => onReview(d.card_id, "reject")}>Reject</button>{d.review && <button className="btn btn-ghost" onClick={() => onReview(d.card_id, "reset")}>Undo</button>}</div></>)}
      {(n.type === "guardrail" || n.type === "exception") && <p>{d.text} <span className="chip">{d.state}</span></p>}
      {(n.type === "unit" || n.type === "related") && (<><p><b>{d.session}</b> · {d.source_type}</p><p>{d.subtopic}</p>{(d.branches ?? []).map((b: string) => <p key={b} className="text-xs">• {b} <i>(dataset rule)</i></p>)}
        {(d.quotes ?? []).map((q: string) => <blockquote key={q} className="quote">“{q}” <span className="text-xs">(verbatim)</span></blockquote>)}{n.type === "related" && <p className="text-xs text-ink/70">Retrieved automatically; not curated or confirmed.</p>}</>)}
      {n.type === "moment" && (<><blockquote className="quote">“{d.quote}”</blockquote><p className="text-xs">Expert, live, {Number(d.ts).toFixed(0)}s, about the {d.slot} slot</p>{d.frame && <img src={api.frameUrl(d.event_id)} alt="Captured screen moment" className="max-h-44 rounded border" />}</>)}
      {n.type === "guideline" && (<><p className="italic">{d.excerpt}</p><p className="text-xs">{d.source}, PDF p.{d.page}. Literature context, not an expert quote and not proof that the rule works in this setting.</p></>)}
      {n.type === "field" && <p>The care-record form field the rules read.</p>}
      {n.type === "route" && <p>A qualified human the record is handed to.</p>}
      <p className="text-xs text-ink/60">{nbr.length} connection{nbr.length === 1 ? "" : "s"}</p>
    </div>
  );
}

/** Force-directed Care Graph: concentric layers (rules inside, evidence outside, everything learned on the rim). */
export function CareGraph() {
  const [data, setData] = useState<CareGraphData | null>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState<string>("");
  const [q, setQ] = useState("");
  const [hide, setHide] = useState<Record<string, boolean>>({ related: true });
  const [frame, setFrame] = useState<{ nodes: N[]; links: L[] }>({ nodes: [], links: [] });
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const sim = useRef<Simulation<N, L> | null>(null);
  const nodes = useRef<N[]>([]);
  const links = useRef<L[]>([]);
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ id: string; moved: boolean } | null>(null);
  const pan = useRef<{ x: number; y: number } | null>(null);

  const load = useCallback(() => { api.graph().then(setData).catch((e) => setErr(explain(e))); }, []);
  useEffect(() => { load(); }, [load]);

  const visible = useMemo(() => {
    if (!data) return { n: [] as GraphNode[], e: [] as GraphEdge[] };
    const keep = new Set(data.nodes.filter((n) => !hide[n.type]).map((n) => n.id));
    // a unit/related node that nothing visible points to is hidden with it
    const e = data.edges.filter((x) => keep.has(x.source) && keep.has(x.target));
    const used = new Set(e.flatMap((x) => [x.source, x.target])); data.nodes.filter((n) => n.type === "rule").forEach((n) => used.add(n.id));
    return { n: data.nodes.filter((n) => keep.has(n.id) && used.has(n.id)), e };
  }, [data, hide]);

  useEffect(() => {
    const old = new Map(nodes.current.map((n) => [n.id, n]));
    nodes.current = visible.n.map((n, i) => { const o = old.get(n.id); const a = (i / Math.max(1, visible.n.length)) * Math.PI * 2; const r = RING[n.type] ?? 300; return { ...n, x: o?.x ?? Math.cos(a) * r, y: o?.y ?? Math.sin(a) * r, vx: 0, vy: 0 }; });
    links.current = visible.e.map((e) => ({ ...e }));
    sim.current?.stop();
    const s = forceSimulation<N>(nodes.current)
      .force("link", forceLink<N, L>(links.current).id((d) => d.id).distance((l) => (l.type === "learned_from" ? 70 : l.type === "re_derives" ? 200 : l.type === "cites" ? 120 : 100)).strength((l) => (l.type === "learned_from" ? 0.05 : 0.5)))
      .force("charge", forceManyBody<N>().strength((d) => (d.type === "learned" ? -10 : d.type === "rule" ? -900 : -120)))
      .force("collide", forceCollide<N>().radius((d) => (d.type === "rule" ? 102 : d.type === "guardrail" || d.type === "exception" ? 78 : d.type === "route" ? 34 : d.type === "learned" ? 10 : 26)))
      .force("radial", forceRadial<N>((d) => RING[d.type] ?? 300, 0, 0).strength((d) => (d.type === "rule" ? 0.3 : d.type === "learned" ? 0.6 : 0.22)))
      .alpha(1).alphaDecay(0.035).on("tick", () => setFrame({ nodes: [...nodes.current], links: [...links.current] }));
    sim.current = s; return () => { s.stop(); };
  }, [visible]);

  const hot = useMemo(() => {
    const focus = sel || "";
    const qq = q.trim().toLowerCase();
    if (!focus && !qq) return null;
    const s = new Set<string>();
    if (focus) { s.add(focus); frame.links.forEach((l) => { if (id(l.source as N) === focus) s.add(id(l.target as N)); if (id(l.target as N) === focus) s.add(id(l.source as N)); }); }
    if (qq) frame.nodes.forEach((n) => { if (n.label.toLowerCase().includes(qq) || JSON.stringify(n.detail).toLowerCase().includes(qq)) s.add(n.id); });
    return s;
  }, [sel, q, frame]);

  const scaleOf = () => { const r = svg.current!.getBoundingClientRect(); return { r, s: Math.min(r.width / 1000, r.height / 840) }; };   // px per viewBox unit
  const toWorld = (cx: number, cy: number) => { const { r, s } = scaleOf(); return { x: ((cx - r.left - r.width / 2) / s - view.x) / view.k, y: ((cy - r.top - r.height / 2) / s - view.y) / view.k }; };
  const onWheel = (e: React.WheelEvent) => { const k = Math.min(2.5, Math.max(0.25, view.k * (e.deltaY < 0 ? 1.1 : 0.9))); setView((v) => ({ ...v, k })); };
  const onDown = (e: React.PointerEvent, nid?: string) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    if (nid) { drag.current = { id: nid, moved: false }; const n = nodes.current.find((x) => x.id === nid)!; n.fx = n.x; n.fy = n.y; sim.current?.alphaTarget(0.25).restart(); e.stopPropagation(); }
    else { const { s: sc } = scaleOf(); pan.current = { x: e.clientX / sc - view.x, y: e.clientY / sc - view.y }; }
  };
  const onMove = (e: React.PointerEvent) => {
    if (drag.current) { const n = nodes.current.find((x) => x.id === drag.current!.id)!; const w = toWorld(e.clientX, e.clientY); n.fx = w.x; n.fy = w.y; drag.current.moved = true; }
    else if (pan.current) { const { s: sc } = scaleOf(); setView((v) => ({ ...v, x: e.clientX / sc - pan.current!.x, y: e.clientY / sc - pan.current!.y })); }
  };
  const onUp = () => {
    if (drag.current) { const n = nodes.current.find((x) => x.id === drag.current!.id)!; n.fx = null; n.fy = null; sim.current?.alphaTarget(0); if (!drag.current.moved) setSel((s) => (s === n.id ? "" : n.id)); drag.current = null; }
    pan.current = null;
  };

  const review = async (rid: string, d: "confirm" | "reject" | "reset") => { await api.review(rid, d); load(); };
  if (err) return <p className="text-coral">{err}</p>;
  if (!data) return <p className="card">Building the graph…</p>;
  const selected = data.nodes.find((n) => n.id === sel) ?? null;
  const st = data.stats;

  return (
    <div className="grid gap-3 lg:grid-cols-[1fr_380px]">
      <section className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <input className="rounded-lg border border-line bg-white px-3 py-1" placeholder="Search: pain, nurse, KU-S13-20…" value={q} onChange={(e) => setQ(e.target.value)} />
          {[["learned", "Learned cards"], ["related", "Related units"], ["unit", "Interview units"], ["guideline", "Guideline"], ["field", "Form fields"]].map(([t, l]) => (
            <label key={t} className="chip cursor-pointer"><input type="checkbox" className="mr-1" checked={!hide[t]} onChange={() => setHide((h) => ({ ...h, [t]: !h[t] }))} />{l} ({st.by_type[t] ?? 0})</label>))}
          <button className="btn btn-ghost" onClick={() => { setView({ x: 0, y: 0, k: 1 }); setSel(""); setQ(""); }}>Reset view</button>
        </div>
        <div className="relative overflow-hidden rounded-2xl border border-line bg-white" style={{ height: "calc(100vh - 270px)", minHeight: 540 }}>
          <svg ref={svg} viewBox="-500 -420 1000 840" preserveAspectRatio="xMidYMid meet" className="h-full w-full touch-none" onWheel={onWheel} onPointerDown={(e) => onDown(e)} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp} role="img" aria-label="Care graph">
            <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
              {[175, 255, 335, 405].map((r) => <circle key={r} r={r} fill="none" stroke="#efeae0" strokeDasharray="3 6" />)}
              {frame.links.map((l, i) => {
                const a = l.source as N, b = l.target as N; if (typeof a === "string" || typeof b === "string") return null;
                const on = !hot || (hot.has(a.id) && hot.has(b.id)); const focus = sel && (a.id === sel || b.id === sel);
                return <g key={i} opacity={on ? 1 : 0.05}><line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={EDGE_COLOR[l.type] ?? "#ccc"} strokeWidth={l.type === "re_derives" ? 2.4 : focus ? 1.8 : 0.9} strokeDasharray={l.type === "related" || l.type === "context" ? "3 3" : undefined} />
                  {(focus || l.type === "re_derives") && l.label && <text x={((a.x ?? 0) + (b.x ?? 0)) / 2} y={((a.y ?? 0) + (b.y ?? 0)) / 2 - 3} fontSize={8} textAnchor="middle" fill="#55666a">{l.label}</text>}</g>;
              })}
              {frame.nodes.map((n) => <g key={n.id} onPointerDown={(e) => onDown(e, n.id)}><title>{n.label}</title>{shape(n, !hot || hot.has(n.id))}
                {(n.type === "unit" || n.type === "related") && hot?.has(n.id) && <text x={(n.x ?? 0) + 9} y={(n.y ?? 0) + 3} fontSize={8}>{n.label}</text>}
                {n.id === sel && <circle cx={n.x} cy={n.y} r={n.type === "rule" ? 0 : 16} fill="none" stroke="#e8a33d" strokeWidth={2} />}</g>)}
            </g>
          </svg>
        </div>
        <div className="flex flex-wrap gap-1 text-[11px]">
          {LEGEND.map(([t, l]) => <span key={t} className="chip">{l}</span>)}
          <span className="chip">solid = confirmed · dashed = hypothesis · teal ring = accepted · red ring = safety-critical</span>
        </div>
        <p className="text-xs text-ink/70">{st.nodes} nodes, {st.edges} connections. The learner independently re-derived {st.rules_rederived_by_learner.length} of the curated rules ({st.rules_rederived_by_learner.join(", ") || "none"}) from the raw interviews. Work Map version {st.map_version}. Scroll to zoom, drag the background to pan, drag nodes to rearrange.</p>
      </section>
      <aside className="space-y-2"><Panel n={selected} g={data} onReview={review} /></aside>
    </div>
  );
}
