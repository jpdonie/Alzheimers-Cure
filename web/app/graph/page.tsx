import { CareGraph } from "@/components/CareGraph";

export default function GraphPage() {
  return (
    <div className="space-y-3">
      <h2 className="text-xl font-bold">Care Graph</h2>
      <p className="text-sm">Every rule, what it tests, who it hands over to, the interview evidence behind it, what you showed live, and everything the apprentice learned from all the interviews, in one map. Click a node to inspect it, confirm or reject it.</p>
      <CareGraph />
    </div>
  );
}
