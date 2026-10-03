// Server-side signed URL so the ElevenLabs key never reaches the browser.
export async function GET(req: Request) {
  const role = new URL(req.url).searchParams.get("role") === "tutor" ? "tutor" : "interviewer";
  const agent = role === "tutor" ? process.env.ELEVENLABS_TUTOR_AGENT_ID : process.env.ELEVENLABS_INTERVIEWER_AGENT_ID;
  const key = process.env.ELEVENLABS_API_KEY;
  if (!agent || !key) return Response.json({ error: "voice not configured" }, { status: 503 });
  try {
    const r = await fetch(`https://api.elevenlabs.io/v1/convai/conversation/get-signed-url?agent_id=${agent}`, {
      headers: { "xi-api-key": key }, signal: AbortSignal.timeout(8000),
    });
    if (!r.ok) return Response.json({ error: "provider error" }, { status: 502 });
    return Response.json({ signedUrl: (await r.json()).signed_url });
  } catch {
    return Response.json({ error: "provider unreachable" }, { status: 504 });
  }
}
