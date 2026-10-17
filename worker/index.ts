/**
 * Fronts the pipeline container.
 *
 * Travel Buddy's `get_places` tool reads R2 directly; when a place has no data
 * it POSTs here to populate it. The container is a long-running server, so the
 * Worker just proxies to it.
 */
import { Container } from "@cloudflare/containers";

interface Env {
  PIPELINE: DurableObjectNamespace<PipelineContainer>;
  ACCOUNT_ID: string;
  ACCESS_KEY_ID: string;
  SECRET_ACCESS_KEY: string;
  SUPADATA_API_KEY: string;
}

export class PipelineContainer extends Container<Env> {
  defaultPort = 8080;

  // Must exceed the longest job. A container that sleeps mid-run kills the
  // background thread doing the work, and the job is lost silently.
  sleepAfter = "30m";

  // Secrets reach the container as environment variables. A getter rather than
  // a field so `this.env` is populated by the time it is read.
  get envVars() {
    return {
      ACCOUNT_ID: this.env.ACCOUNT_ID,
      ACCESS_KEY_ID: this.env.ACCESS_KEY_ID,
      SECRET_ACCESS_KEY: this.env.SECRET_ACCESS_KEY,
      SUPADATA_API_KEY: this.env.SUPADATA_API_KEY,
    };
  }
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

/** Hand the job to the single container instance. */
async function dispatch(env: Env, body: { url: string; city?: string }) {
  const container = env.PIPELINE.getByName("pipeline");
  return container.fetch(
    new Request("http://container/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { pathname } = new URL(request.url);

    // One video per city: `discover_content` picks the single best vlog.
    if (pathname === "/process" && request.method === "POST") {
      let body: { url?: string; city?: string };
      try {
        body = await request.json();
      } catch {
        return json({ error: "invalid json" }, 400);
      }
      if (!body.url) return json({ error: "url is required" }, 400);

      return dispatch(env, { url: body.url, city: body.city });
    }

    return json({ error: "not found" }, 404);
  },

  async scheduled(_event: ScheduledController, _env: Env): Promise<void> {
    // TODO: decide what the weekly run should process.
    //
    // There is no work list in this repo any more -- R2 is the only state, and
    // it records what is *done*, not what is pending. Turning a city into video
    // URLs is `get_videos`, which lives in Travel Buddy.
    //
    // So this handler needs one of:
    //   - a list of URLs to refresh, stored somewhere this Worker can read
    //   - Travel Buddy calling /process on a schedule instead, and this cron
    //     being dropped entirely
    console.log("scheduled run: no work source configured");
  },
};
