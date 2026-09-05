const SERVICE = "KBM-VIDEO-STUDIO-GITHUB-ACTIONS-FREE-13";
const VERSION = "0.13.0";
const GITHUB_API = "https://api.github.com";
const GITHUB_UPLOADS = "https://uploads.github.com";
const GITHUB_API_VERSION = "2026-03-10";
const MAX_JSON_BYTES = 256 * 1024;
const MAX_UPLOAD_BYTES = 95 * 1024 * 1024;
const JOB_ID_RE = /^[a-f0-9-]{36}$/;
const EXTENSION_RE = /^(mp4|mov|m4v|mkv|webm)$/;
const OWNER_RE = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/;
const REPOSITORY_RE = /^[A-Za-z0-9._-]{1,100}$/;
const REF_RE = /^(?!.*\.\.)(?!\/)(?!.*\/$)[A-Za-z0-9._/-]{1,200}$/;
const WORKFLOW_RE = /^[A-Za-z0-9._-]{1,100}\.ya?ml$/;
const BRIEF_B64_RE = /^[A-Za-z0-9_-]{0,1600}$/;
const ALLOWED_TEMPLATES = new Set([
  "KBM-V01-INFOGRAPHIC",
  "KBM-V02-PRESENTER-UI",
  "KBM-V03-MACHINE-REVIEW",
  "KBM-V04-MOTION-POSTER",
  "KBM-V05-TECHNICAL-VFX",
  "KBM-V06-STORY-REVEAL",
]);
const ALLOWED_VOICES = new Set([
  "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse",
]);
const ALLOWED_EDIT_STYLES = new Set(["balanced", "cinematic", "high-energy"]);

type JsonObject = Record<string, unknown>;

type JobOptions = {
  extension: string;
  creativePreset: string;
  template: string;
  voice: string;
  maxSeconds: number;
  campaignBriefB64: string;
  editStyle: string;
};

type GitHubAsset = {
  id: number;
  name: string;
  size: number;
  state: string;
};

type GitHubRelease = {
  id: number;
  tagName: string;
  assets: GitHubAsset[];
};

type GitHubRun = {
  id: number;
  status: string;
  conclusion: string | null;
  event: string;
  headBranch: string;
  workflowPath: string;
};

class HttpError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) {
    super(message);
  }
}

function json(payload: JsonObject, status = 200, extraHeaders: HeadersInit = {}): Response {
  return Response.json(payload, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      ...extraHeaders,
    },
  });
}

function asObject(value: unknown, label: string): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new HttpError(502, "INVALID_UPSTREAM_RESPONSE", `${label} returned an invalid response`);
  }
  return value as JsonObject;
}

function positiveInteger(value: unknown, label: string): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 1) {
    throw new HttpError(502, "INVALID_UPSTREAM_RESPONSE", `${label} is invalid`);
  }
  return parsed;
}

function stringValue(value: unknown, label: string, max = 400): string {
  if (typeof value !== "string" || !value.trim() || value.length > max) {
    throw new HttpError(502, "INVALID_UPSTREAM_RESPONSE", `${label} is invalid`);
  }
  return value.trim();
}

async function readJsonLimited(response: Response, maxBytes = MAX_JSON_BYTES): Promise<unknown> {
  const declared = Number(response.headers.get("content-length") || "0");
  if (declared > maxBytes) throw new HttpError(502, "UPSTREAM_RESPONSE_TOO_LARGE", "Upstream JSON is too large");
  if (!response.body) throw new HttpError(502, "INVALID_UPSTREAM_RESPONSE", "Upstream response has no body");

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maxBytes) {
      await reader.cancel();
      throw new HttpError(502, "UPSTREAM_RESPONSE_TOO_LARGE", "Upstream JSON is too large");
    }
    chunks.push(value);
  }

  const merged = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return JSON.parse(new TextDecoder().decode(merged));
  } catch {
    throw new HttpError(502, "INVALID_UPSTREAM_RESPONSE", "Upstream response is not valid JSON");
  }
}

async function timingSafeEqual(left: string, right: string): Promise<boolean> {
  const encoder = new TextEncoder();
  const a = encoder.encode(left);
  const b = encoder.encode(right);
  if (a.byteLength !== b.byteLength) return false;
  const subtle = crypto.subtle as SubtleCrypto & {
    timingSafeEqual(first: ArrayBufferView, second: ArrayBufferView): boolean;
  };
  return subtle.timingSafeEqual(a, b);
}

async function requireBearer(request: Request, env: Env): Promise<void> {
  const header = request.headers.get("authorization") || "";
  const supplied = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (!env.KBM_STUDIO_TOKEN || !(await timingSafeEqual(supplied, env.KBM_STUDIO_TOKEN))) {
    throw new HttpError(401, "UNAUTHORIZED", "Studio token is missing or invalid");
  }
}

function requireConfig(env: Env): void {
  if (!env.KBM_STUDIO_TOKEN || !env.KBM_GITHUB_TOKEN) {
    throw new HttpError(503, "SERVICE_NOT_CONFIGURED", "Required secrets are missing");
  }
  if (!OWNER_RE.test(env.KBM_GITHUB_OWNER || "") || !REPOSITORY_RE.test(env.KBM_GITHUB_REPO || "")) {
    throw new HttpError(503, "SERVICE_NOT_CONFIGURED", "GitHub repository configuration is invalid");
  }
  if (!REF_RE.test(env.KBM_GITHUB_REF || "") || !WORKFLOW_RE.test(env.KBM_GITHUB_WORKFLOW || "")) {
    throw new HttpError(503, "SERVICE_NOT_CONFIGURED", "GitHub workflow configuration is invalid");
  }
}

function githubHeaders(env: Env, accept = "application/vnd.github+json"): Headers {
  return new Headers({
    Accept: accept,
    Authorization: `Bearer ${env.KBM_GITHUB_TOKEN}`,
    "User-Agent": "kbm-video-studio-free-13",
    "X-GitHub-Api-Version": GITHUB_API_VERSION,
  });
}

function repositoryPath(env: Env, suffix: string): string {
  return `/repos/${env.KBM_GITHUB_OWNER}/${env.KBM_GITHUB_REPO}${suffix}`;
}

async function githubRequest(env: Env, path: string, init: RequestInit = {}): Promise<Response> {
  const headers = githubHeaders(env);
  new Headers(init.headers).forEach((value, key) => headers.set(key, value));
  return fetch(`${GITHUB_API}${path}`, {...init, headers});
}

async function githubJson(env: Env, path: string, init: RequestInit = {}): Promise<unknown> {
  const response = await githubRequest(env, path, init);
  if (!response.ok) {
    console.error(JSON.stringify({event: "github_api_error", path, status: response.status}));
    throw new HttpError(502, "GITHUB_API_ERROR", `GitHub API returned HTTP ${response.status}`);
  }
  return readJsonLimited(response);
}

function parseAsset(value: unknown): GitHubAsset | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const candidate = value as JsonObject;
  const id = Number(candidate.id);
  const size = Number(candidate.size);
  if (!Number.isSafeInteger(id) || id < 1 || !Number.isSafeInteger(size) || size < 0) return null;
  if (typeof candidate.name !== "string" || typeof candidate.state !== "string") return null;
  return {id, name: candidate.name, size, state: candidate.state};
}

function parseRelease(value: unknown): GitHubRelease {
  const object = asObject(value, "GitHub release");
  const assets = Array.isArray(object.assets) ? object.assets.map(parseAsset).filter((asset): asset is GitHubAsset => asset !== null) : [];
  return {
    id: positiveInteger(object.id, "release id"),
    tagName: stringValue(object.tag_name, "release tag", 120),
    assets,
  };
}

function parseRun(value: unknown): GitHubRun {
  const object = asObject(value, "GitHub workflow run");
  const [workflowPath = ""] = stringValue(object.path, "workflow path", 300).split("@", 1);
  return {
    id: positiveInteger(object.id, "workflow run id"),
    status: stringValue(object.status, "workflow status", 40),
    conclusion: object.conclusion === null ? null : stringValue(object.conclusion, "workflow conclusion", 40),
    event: stringValue(object.event, "workflow event", 40),
    headBranch: stringValue(object.head_branch, "workflow branch", 200),
    workflowPath,
  };
}

function validateCampaignBriefB64(value: string): string {
  const encoded = value.trim();
  if (!BRIEF_B64_RE.test(encoded)) throw new HttpError(400, "INVALID_CAMPAIGN_BRIEF", "Campaign brief encoding is invalid");
  if (!encoded) return "";
  try {
    const normalized = encoded.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized + "=".repeat((4 - normalized.length % 4) % 4);
    const binary = atob(padded);
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    const decoded = new TextDecoder("utf-8", {fatal: true}).decode(bytes).replace(/\u0000/g, " ").trim();
    if (!decoded || decoded.length > 600) throw new Error("invalid length");
  } catch {
    throw new HttpError(400, "INVALID_CAMPAIGN_BRIEF", "Campaign brief encoding is invalid");
  }
  return encoded;
}

function parseJobOptions(request: Request): JobOptions {
  const extension = (request.headers.get("x-kbm-extension") || "").toLowerCase();
  const creativePreset = request.headers.get("x-kbm-preset") || "";
  const template = request.headers.get("x-kbm-template") || "";
  const voice = request.headers.get("x-kbm-voice") || "";
  const maxSeconds = Number(request.headers.get("x-kbm-max-seconds") || "0");
  const campaignBriefB64 = validateCampaignBriefB64(request.headers.get("x-kbm-brief-b64") || "");
  const editStyle = request.headers.get("x-kbm-edit-style") || "high-energy";
  if (!EXTENSION_RE.test(extension)) throw new HttpError(400, "UNSUPPORTED_MEDIA", "Unsupported video extension");
  if (!/^[A-Za-z0-9_-]{1,100}$/.test(creativePreset)) throw new HttpError(400, "INVALID_PRESET", "Creative preset is invalid");
  if (!ALLOWED_TEMPLATES.has(template)) throw new HttpError(400, "INVALID_TEMPLATE", "Template is invalid");
  if (!ALLOWED_VOICES.has(voice)) throw new HttpError(400, "INVALID_VOICE", "Voice is invalid");
  if (!ALLOWED_EDIT_STYLES.has(editStyle)) throw new HttpError(400, "INVALID_EDIT_STYLE", "Edit style is invalid");
  if (!Number.isInteger(maxSeconds) || maxSeconds < 5 || maxSeconds > 90) {
    throw new HttpError(400, "INVALID_DURATION", "Duration must be between 5 and 90 seconds");
  }
  return {extension, creativePreset, template, voice, maxSeconds, campaignBriefB64, editStyle};
}

function requestUploadSize(request: Request): number {
  const size = Number(request.headers.get("content-length") || "0");
  if (!Number.isSafeInteger(size) || size < 1 || size > MAX_UPLOAD_BYTES) {
    throw new HttpError(413, "INVALID_UPLOAD_SIZE", "Video must be between 1 byte and 95 MiB");
  }
  const contentType = (request.headers.get("content-type") || "").toLowerCase();
  if (!(contentType.startsWith("video/") || contentType === "application/octet-stream")) {
    throw new HttpError(415, "INVALID_CONTENT_TYPE", "Upload must be a video binary stream");
  }
  if (!request.body) throw new HttpError(400, "EMPTY_UPLOAD", "Video body is missing");
  return size;
}

function jobTag(jobId: string): string {
  return `kbm-job-${jobId}`;
}

function routeJobId(pathname: string, suffix = ""): string {
  const escapedSuffix = suffix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = pathname.match(new RegExp(`^/v1/jobs/([a-f0-9-]{36})${escapedSuffix}$`));
  const jobId = match?.[1];
  if (!jobId || !JOB_ID_RE.test(jobId)) throw new HttpError(404, "NOT_FOUND", "Route not found");
  return jobId;
}

async function createDraftRelease(env: Env, jobId: string): Promise<GitHubRelease> {
  const value = await githubJson(env, repositoryPath(env, "/releases"), {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      tag_name: jobTag(jobId),
      target_commitish: env.KBM_GITHUB_REF,
      name: `KBM private render job ${jobId}`,
      body: "Temporary unpublished render job. Automatically removed after 48 hours.",
      draft: true,
      prerelease: false,
      generate_release_notes: false,
    }),
  });
  const release = parseRelease(value);
  if (release.tagName !== jobTag(jobId)) throw new HttpError(502, "GITHUB_RELEASE_MISMATCH", "GitHub created an unexpected release");
  return release;
}

async function uploadInputAsset(
  request: Request,
  env: Env,
  release: GitHubRelease,
  jobId: string,
  options: JobOptions,
  size: number,
): Promise<GitHubAsset> {
  const name = `input-${jobId}.${options.extension}`;
  const headers = githubHeaders(env);
  headers.set("Content-Type", request.headers.get("content-type") || "application/octet-stream");
  headers.set("Content-Length", String(size));
  const url = `${GITHUB_UPLOADS}${repositoryPath(env, `/releases/${release.id}/assets`)}?name=${encodeURIComponent(name)}`;
  const response = await fetch(url, {method: "POST", headers, body: request.body});
  if (!response.ok) {
    console.error(JSON.stringify({event: "github_upload_error", status: response.status}));
    throw new HttpError(502, "GITHUB_UPLOAD_ERROR", `GitHub upload returned HTTP ${response.status}`);
  }
  const asset = parseAsset(await readJsonLimited(response));
  if (!asset || asset.name !== name || asset.size !== size || asset.state !== "uploaded") {
    throw new HttpError(502, "GITHUB_UPLOAD_MISMATCH", "GitHub upload validation failed");
  }
  return asset;
}

async function dispatchWorkflow(
  env: Env,
  jobId: string,
  release: GitHubRelease,
  inputAsset: GitHubAsset,
  options: JobOptions,
): Promise<GitHubRun> {
  const workflow = encodeURIComponent(env.KBM_GITHUB_WORKFLOW);
  const value = await githubJson(env, repositoryPath(env, `/actions/workflows/${workflow}/dispatches`), {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      ref: env.KBM_GITHUB_REF,
      inputs: {
        job_id: jobId,
        release_id: String(release.id),
        input_asset_id: String(inputAsset.id),
        extension: options.extension,
        creative_preset: options.creativePreset,
        template: options.template,
        voice: options.voice,
        max_seconds: String(options.maxSeconds),
        campaign_brief_b64: options.campaignBriefB64,
        edit_style: options.editStyle,
      },
    }),
  });
  const object = asObject(value, "workflow dispatch");
  return {
    id: positiveInteger(object.workflow_run_id, "workflow run id"),
    status: "queued",
    conclusion: null,
    event: "workflow_dispatch",
    headBranch: env.KBM_GITHUB_REF,
    workflowPath: `.github/workflows/${env.KBM_GITHUB_WORKFLOW}`,
  };
}

async function bestEffortDelete(env: Env, path: string): Promise<void> {
  try {
    const response = await githubRequest(env, path, {method: "DELETE"});
    if (!(response.ok || response.status === 404)) {
      console.error(JSON.stringify({event: "github_cleanup_error", path, status: response.status}));
    }
  } catch (error) {
    console.error(JSON.stringify({event: "github_cleanup_error", path, message: error instanceof Error ? error.message : "unknown"}));
  }
}

async function cleanupJob(env: Env, releaseId: number, jobId: string): Promise<void> {
  await bestEffortDelete(env, repositoryPath(env, `/releases/${releaseId}`));
  await bestEffortDelete(env, repositoryPath(env, `/git/refs/tags/${jobTag(jobId)}`));
}

async function createJob(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  requireConfig(env);
  const options = parseJobOptions(request);
  const size = requestUploadSize(request);
  const jobId = crypto.randomUUID();
  const release = await createDraftRelease(env, jobId);
  try {
    const inputAsset = await uploadInputAsset(request, env, release, jobId, options, size);
    const run = await dispatchWorkflow(env, jobId, release, inputAsset, options);
    return json({
      ok: true,
      jobId,
      releaseId: release.id,
      runId: run.id,
      state: "queued",
      progress: 60,
      message: "فایل دریافت شد و رندر رایگان در صف GitHub Actions قرار گرفت",
    }, 202);
  } catch (error) {
    ctx.waitUntil(cleanupJob(env, release.id, jobId));
    throw error;
  }
}

function queryId(url: URL, name: string): number {
  const value = Number(url.searchParams.get(name) || "0");
  if (!Number.isSafeInteger(value) || value < 1) throw new HttpError(400, "INVALID_JOB_REFERENCE", `${name} is invalid`);
  return value;
}

async function getRelease(env: Env, releaseId: number, jobId: string): Promise<GitHubRelease> {
  const release = parseRelease(await githubJson(env, repositoryPath(env, `/releases/${releaseId}`)));
  if (release.tagName !== jobTag(jobId)) throw new HttpError(403, "JOB_REFERENCE_MISMATCH", "Release does not belong to this job");
  return release;
}

async function getRun(env: Env, runId: number, jobId: string): Promise<GitHubRun> {
  const run = parseRun(await githubJson(env, repositoryPath(env, `/actions/runs/${runId}`)));
  const expectedWorkflowPath = `.github/workflows/${env.KBM_GITHUB_WORKFLOW}`;
  if (
    run.id !== runId ||
    run.event !== "workflow_dispatch" ||
    run.headBranch !== env.KBM_GITHUB_REF ||
    run.workflowPath !== expectedWorkflowPath
  ) {
    throw new HttpError(403, "JOB_REFERENCE_MISMATCH", "Workflow run does not belong to this job");
  }
  return run;
}

function assetNamed(release: GitHubRelease, name: string): GitHubAsset | undefined {
  return release.assets.find((asset) => asset.name === name && asset.state === "uploaded");
}

async function getJob(env: Env, url: URL): Promise<Response> {
  requireConfig(env);
  const jobId = routeJobId(url.pathname);
  const releaseId = queryId(url, "releaseId");
  const runId = queryId(url, "runId");
  const [release, run] = await Promise.all([getRelease(env, releaseId, jobId), getRun(env, runId, jobId)]);
  const finalAsset = assetNamed(release, `final-${jobId}.mp4`);
  const failureAsset = assetNamed(release, `failure-${jobId}.json`);

  if (run.status === "completed") {
    if (run.conclusion === "success" && finalAsset && finalAsset.size > 1024) {
      return json({ok: true, jobId, state: "ready", progress: 100, message: "ویدیوی نهایی آماده دانلود است"});
    }
    return json({
      ok: false,
      jobId,
      state: "failed",
      progress: 0,
      message: failureAsset ? "رندر ناموفق بود؛ گزارش کنترل‌شده در Job ثبت شد" : "رندر GitHub Actions ناموفق بود",
    });
  }

  const inProgress = run.status === "in_progress";
  return json({
    ok: true,
    jobId,
    state: inProgress ? "rendering" : "queued",
    progress: inProgress ? 78 : 65,
    message: inProgress ? "تحقیق رسانه، تدوین و رندر در GitHub Actions در حال اجراست" : "Job در صف رایگان GitHub Actions است",
  });
}

async function ticketSignature(secret: string, jobId: string, assetId: number, expires: number): Promise<string> {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), {name: "HMAC", hash: "SHA-256"}, false, ["sign"]);
  const data = encoder.encode(`${jobId}:${assetId}:${expires}`);
  const signature = new Uint8Array(await crypto.subtle.sign("HMAC", key, data));
  return Array.from(signature, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function createDownloadTicket(env: Env, url: URL): Promise<Response> {
  requireConfig(env);
  const jobId = routeJobId(url.pathname, "/download-ticket");
  const releaseId = queryId(url, "releaseId");
  const release = await getRelease(env, releaseId, jobId);
  const asset = assetNamed(release, `final-${jobId}.mp4`);
  if (!asset || asset.size < 1024) throw new HttpError(404, "OUTPUT_NOT_READY", "Final MP4 is not ready");
  const expires = Math.floor(Date.now() / 1000) + 300;
  const ticket = await ticketSignature(env.KBM_STUDIO_TOKEN, jobId, asset.id, expires);
  const query = new URLSearchParams({assetId: String(asset.id), expires: String(expires), ticket});
  return json({ok: true, url: `/v1/jobs/${jobId}/download?${query}`, expires});
}

async function requireDownloadTicket(env: Env, url: URL, jobId: string): Promise<number> {
  const assetId = queryId(url, "assetId");
  const expires = Number(url.searchParams.get("expires") || "0");
  const ticket = url.searchParams.get("ticket") || "";
  const now = Math.floor(Date.now() / 1000);
  if (!Number.isInteger(expires) || expires < now || expires > now + 300 || !/^[a-f0-9]{64}$/.test(ticket)) {
    throw new HttpError(401, "INVALID_TICKET", "Download ticket is invalid or expired");
  }
  const expected = await ticketSignature(env.KBM_STUDIO_TOKEN, jobId, assetId, expires);
  if (!(await timingSafeEqual(ticket, expected))) throw new HttpError(401, "INVALID_TICKET", "Download ticket is invalid or expired");
  return assetId;
}

function allowedAssetLocation(location: string): URL {
  const url = new URL(location);
  const allowedHost = url.hostname === "objects.githubusercontent.com" || url.hostname.endsWith(".githubusercontent.com");
  if (url.protocol !== "https:" || !allowedHost) throw new HttpError(502, "UNSAFE_ASSET_REDIRECT", "GitHub returned an unsafe asset location");
  return url;
}

async function downloadAsset(env: Env, assetId: number): Promise<Response> {
  let response = await githubRequest(env, repositoryPath(env, `/releases/assets/${assetId}`), {
    headers: {Accept: "application/octet-stream"},
    redirect: "manual",
  });
  if (response.status === 302) {
    const location = response.headers.get("location") || "";
    response = await fetch(allowedAssetLocation(location), {redirect: "follow"});
  }
  if (!response.ok || !response.body) throw new HttpError(502, "GITHUB_DOWNLOAD_ERROR", `GitHub download returned HTTP ${response.status}`);
  const headers = new Headers({
    "Content-Type": "video/mp4",
    "Content-Disposition": `attachment; filename="kbm-video-${assetId}.mp4"`,
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
  });
  const length = response.headers.get("content-length");
  if (length) headers.set("Content-Length", length);
  return new Response(response.body, {headers});
}

async function downloadJob(env: Env, url: URL): Promise<Response> {
  requireConfig(env);
  const jobId = routeJobId(url.pathname, "/download");
  const assetId = await requireDownloadTicket(env, url, jobId);
  return downloadAsset(env, assetId);
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/v1/health" && request.method === "GET") {
        return json({ok: true, service: SERVICE, version: VERSION, runner: "github-actions-free", editorial: "package13-ready"});
      }
      if (/^\/v1\/jobs\/[a-f0-9-]{36}\/download$/.test(url.pathname) && request.method === "GET") {
        return await downloadJob(env, url);
      }
      if (url.pathname.startsWith("/v1/")) await requireBearer(request, env);
      if (url.pathname === "/v1/jobs" && request.method === "POST") return await createJob(request, env, ctx);
      if (/^\/v1\/jobs\/[a-f0-9-]{36}$/.test(url.pathname) && request.method === "GET") return await getJob(env, url);
      if (/^\/v1\/jobs\/[a-f0-9-]{36}\/download-ticket$/.test(url.pathname) && request.method === "POST") {
        return await createDownloadTicket(env, url);
      }
      if (url.pathname.startsWith("/v1/")) throw new HttpError(404, "NOT_FOUND", "Route not found");
      return env.ASSETS.fetch(request);
    } catch (error) {
      if (error instanceof HttpError) return json({ok: false, error: error.code, message: error.message}, error.status);
      console.error(JSON.stringify({event: "worker_error", path: url.pathname, message: error instanceof Error ? error.message : "unknown"}));
      return json({ok: false, error: "INTERNAL_ERROR", message: "Unexpected service error"}, 500);
    }
  },
} satisfies ExportedHandler<Env>;
