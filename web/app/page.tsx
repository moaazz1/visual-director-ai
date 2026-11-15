"use client";

import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";

const categories = {
  concept: "Concept & message", composition: "Composition & hierarchy", hero: "Hero placement",
  camera: "Camera & perspective", lighting: "Lighting design", color: "Color & brand",
  styling: "Art direction & styling", performance: "Pose & expression",
  realism: "Realism & retouching", effectiveness: "Copy space & effectiveness",
};
const brandFields = {
  name: "Profile name", colors: "Brand colors", style: "Visual style", hero: "Hero placement",
  copy_space: "Copy space", lighting: "Lighting direction", photography: "Photographic treatment",
  locked: "Locked elements", negative: "Exclusions",
};
type Brand = Record<keyof typeof brandFields, string>;
type Finding = {observation: string; assumption: string; recommendation: string; rationale: string};
type Treatment = {name: string; direction: string; rationale: string; changes: string[]; preserve: string[]; avoid: string[]};
type Asset = {id: string; filename: string; width: number; height: number; size: number};
type Audit = {id: string; result: {
  verdict: string; preserve: string[]; priorities: {issue: string; action: string; rationale: string}[];
  review: Record<keyof typeof categories, Finding>; treatments: Treatment[];
}};
type SavedPrompt = {text: string; treatment: string};
type Config = {vision_configured: boolean; credential_name: string; sample_brand: Brand};
type Restore = {asset: Asset; audit: Audit | null; request?: {brief: string; brand: Brand | null}; prompt: SavedPrompt | null};
const assetKey = "visual-director-current-asset";

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(typeof detail === "string" ? detail :
      Array.isArray(detail) ? detail.map((item: {loc: string[]; msg: string}) => `${item.loc.slice(1).join(".")}: ${item.msg}`).join(" · ") :
      "Request failed. Please retry.");
  }
  return response.json();
}

function post<T>(path: string, data: unknown) {
  return api<T>(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
}

const errorText = (error: unknown) => error instanceof Error ? error.message : "Something went wrong. Please retry.";

function Icon({kind, className = ""}: {kind: "mark" | "image" | "upload" | "arrow" | "spark"; className?: string}) {
  const paths = {
    mark: <><circle cx="12" cy="12" r="7"/><path d="M12 1v6m0 10v6M1 12h6m10 0h6"/><circle cx="12" cy="12" r="1" fill="currentColor"/></>,
    image: <><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="9" r="1.5"/><path d="m3 17 5-4 4 4 4-6 5 5"/></>,
    upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5"/></>,
    arrow: <path d="M4 12h15m-6-6 6 6-6 6"/>,
    spark: <path d="M12 2c0 6-4 10-10 10 6 0 10 4 10 10 0-6 4-10 10-10-6 0-10-4-10-10Z"/>,
  };
  return <svg aria-hidden="true" className={className} width="24" height="24" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">{paths[kind]}</svg>;
}

export default function Studio() {
  const [config, setConfig] = useState<Config | null>(null);
  const [configError, setConfigError] = useState("");
  const [asset, setAsset] = useState<Asset | null>(null);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [brief, setBrief] = useState("");
  const [brand, setBrand] = useState<Brand | null>(null);
  const [treatment, setTreatment] = useState("");
  const [prompt, setPrompt] = useState("");
  const [promptTreatment, setPromptTreatment] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dragging, setDragging] = useState(false);
  const [zoom, setZoom] = useState(100);
  const fileInput = useRef<HTMLInputElement>(null);
  const lock = useRef(false);

  async function loadConfig() {
    setConfigError("");
    try { setConfig(await api<Config>("config")); }
    catch (cause) { setConfigError(errorText(cause)); }
  }

  useEffect(() => {
    void loadConfig();
    const previous = localStorage.getItem(assetKey);
    if (!previous) return;
    lock.current = true;
    setBusy("Restoring workspace");
    api<Restore>(`assets/${previous}/audit`).then(data => {
      setAsset(data.asset);
      setAudit(data.audit);
      setBrief(data.request?.brief ?? "");
      setBrand(data.request?.brand ?? null);
      setTreatment(data.prompt?.treatment ?? data.audit?.result.treatments[0].name ?? "");
      setPrompt(data.prompt?.text ?? "");
      setPromptTreatment(data.prompt?.treatment ?? "");
    }).catch(cause => {
      setError(errorText(cause));
    }).finally(() => {
      lock.current = false;
      setBusy("");
    });
  }, []);

  async function run(label: string, action: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true;
    setBusy(label);
    setError("");
    setNotice("");
    try { await action(); }
    catch (cause) { setError(errorText(cause)); }
    finally { lock.current = false; setBusy(""); }
  }

  async function sendImage(file: File) {
    if (file.size > 15 * 1024 * 1024) throw new Error("Choose an image up to 15 MiB.");
    const body = new FormData();
    body.set("file", file);
    const uploaded = await api<Asset>("assets", {method: "POST", body});
    localStorage.setItem(assetKey, uploaded.id);
    setAsset(uploaded);
    setAudit(null);
    setTreatment("");
    setPrompt("");
    setPromptTreatment("");
    setZoom(100);
  }

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void run("Uploading image", () => sendImage(file));
    event.target.value = "";
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void run("Uploading image", () => sendImage(file));
  }

  function loadSample() {
    return run("Loading sample", async () => {
      const result = await fetch("/sample-campaign.jpg");
      if (!result.ok) throw new Error("The sample image is unavailable.");
      await sendImage(new File([await result.blob()], "Cherry Still Life.jpg", {type: "image/jpeg"}));
    });
  }

  function analyze() {
    if (!asset) return;
    void run("Analyzing image", async () => {
      const response = await post<Audit>("audits", {asset_id: asset.id, brief, brand});
      setAudit(response);
      setTreatment(response.result.treatments[0].name);
      setPrompt("");
      setPromptTreatment("");
      setNotice("Creative audit complete.");
    });
  }

  function updatePrompt(save: boolean) {
    if (!audit || (save && (!prompt.trim() || promptTreatment !== treatment))) return;
    void run(save ? "Saving prompt" : "Building prompt", async () => {
      const result = await post<SavedPrompt>(`audits/${audit.id}/prompts`, {treatment, ...(save ? {text: prompt} : {})});
      setPrompt(result.text);
      setPromptTreatment(result.treatment);
      setNotice(save ? "Prompt revision saved." : "Production prompt generated and saved.");
    });
  }

  function download() {
    const url = URL.createObjectURL(new Blob([prompt], {type: "text/plain;charset=utf-8"}));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "visual-director-editing-prompt.txt";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const promptReady = !!prompt && promptTreatment === treatment;

  return <>
    <header className="topbar">
      <div className="flex items-center gap-3"><span className="logo"><Icon kind="mark"/></span>
        <strong>Visual Director <span className="accent">AI</span></strong></div>
      <span className="workspace-tag">Creative workspace</span>
    </header>
    <main className="shell">
      <div className="intro">
        <div><h1>Creative review</h1><p>Audit an advertising image and turn the findings into production direction.</p></div>
        <div className="provider"><span className={config?.vision_configured ? "dot on" : "dot"}/>{configError ? "API unavailable" : config ? (config.vision_configured ? "Vision configured" : "Vision setup required") : "Checking configuration"}</div>
      </div>
      {(configError || config?.vision_configured === false) && <div className="banner config-banner" role="status">
        {configError || <>Set <code>{config?.credential_name}</code> on the FastAPI server and restart it to run an AI audit.</>}
        <button className="text-button" onClick={() => void loadConfig()}>Check connection</button>
      </div>}
      {error && <div className="banner error-banner" role="alert">{error}<button className="text-button" onClick={() => setError("")}>Dismiss</button></div>}
      {(busy || notice) && <div className="banner status-banner" role="status">{busy && <span className="spinner"/>}{busy || notice}</div>}
      <div className="workspace">
        <section className="image-column" aria-labelledby="image-title">
          <div className="section-bar"><h2 id="image-title">Reference image</h2>
            {asset && <button className="text-button" disabled={!!busy} onClick={() => fileInput.current?.click()}>Replace image</button>}
          </div>
          <input hidden ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" onChange={onFile}/>
          <div className={`stage ${dragging ? "dragging" : ""}`} onDragOver={event => {event.preventDefault(); if (!busy) setDragging(true);}} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
            {asset ? <div className="frame">
              {/* The original is served by an authenticated same-origin endpoint. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/api/assets/${asset.id}/image`} alt="Uploaded advertising reference" style={{transform: `scale(${zoom / 100})`}}/>
            </div> : <div className="empty-stage">
              <span className="image-icon"><Icon kind="image"/></span>
              <h3>Add an advertising image</h3><p>Drop a JPG, PNG or WebP up to 15 MiB.</p>
              <button className="primary" disabled={!!busy} onClick={() => fileInput.current?.click()}><Icon kind="upload"/> Choose image</button>
              <button className="text-button" disabled={!!busy} onClick={() => void loadSample()}>Use sample image <Icon kind="arrow"/></button>
            </div>}
          </div>
          {asset && <div className="image-meta">
            <div><strong>{asset.filename}</strong><small>{asset.width} × {asset.height} px · {(asset.size / 1048576).toFixed(2)} MiB</small></div>
            <label className="zoom">Zoom <select value={zoom} onChange={event => setZoom(Number(event.target.value))}>
              {[100, 125, 150, 200].map(value => <option key={value} value={value}>{value}%</option>)}
            </select></label>
          </div>}
        </section>
        <section className="direction" aria-labelledby="direction-title">
          <div className="section-bar"><h2 id="direction-title">Creative direction</h2><Icon kind="spark" className="accent small-icon"/></div>
          <div className="panel">
            <label className="field">Brand profile<select disabled={!config || !!busy} value={brand ? "sample" : ""} onChange={event => setBrand(event.target.value && config ? {...config.sample_brand} : null)}>
              <option value="">No brand profile</option><option value="sample">Ooredoo Oman · editable sample</option>
            </select></label>
            {brand && <details className="brand-editor"><summary>Edit profile for this review</summary><div className="brand-fields">
              {(Object.keys(brandFields) as (keyof Brand)[]).map(key => <label key={key} className="field">{brandFields[key]}
                <textarea disabled={!!busy} value={brand[key]} maxLength={key === "name" ? 120 : 500} rows={key === "name" ? 1 : 2}
                  onChange={event => setBrand({...brand, [key]: event.target.value})}/>
              </label>)}
            </div></details>}
            <label className="field brief">Creative brief <textarea placeholder="Campaign objective, audience, format or elements to preserve…" rows={4} value={brief}
              onChange={event => setBrief(event.target.value)} maxLength={4000} disabled={!!busy}/></label>
            <button className="primary wide" disabled={!asset || !config?.vision_configured || !!busy} onClick={analyze}><Icon kind="spark"/> {audit ? "Run a new creative audit" : "Run creative audit"}</button>
          </div>
          <div className="verdict">
            <h2>Director’s verdict</h2>
            {audit ? <>
              <p className="verdict-copy">{audit.result.verdict}</p>
              <h3>Priority fixes</h3>
              <ol className="priorities">{audit.result.priorities.map((item, index) => <li key={index}>
                <b>{item.issue}</b><p>{item.action}</p><small>{item.rationale}</small>
              </li>)}</ol>
              {!!audit.result.preserve.length && <><h3>Preserve</h3><ul className="list">{audit.result.preserve.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
              <h3>Detailed review</h3>
              {(Object.keys(categories) as (keyof typeof categories)[]).map(key => {
                const finding = audit.result.review[key];
                return <details key={key} className="finding"><summary>{categories[key]}</summary>
                  <dl><dt>Observation</dt><dd>{finding.observation}</dd><dt>Assumption</dt><dd>{finding.assumption}</dd>
                    <dt>Recommendation</dt><dd>{finding.recommendation}</dd><dt>Rationale</dt><dd>{finding.rationale}</dd></dl>
                </details>;
              })}
            </> : <p className="muted">{asset ? "The verdict, ranked fixes and photographic recommendations will appear after the audit." : "Upload a reference to start the review."}</p>}
          </div>
        </section>
      </div>
      {audit && <section className="production" aria-labelledby="production-title">
        <h2 id="production-title">Creative treatments</h2>
        <fieldset className="treatments" aria-label="Choose a creative treatment">
          {audit.result.treatments.map(item => <label key={item.name} className={`treatment ${treatment === item.name ? "selected" : ""}`}>
            <input type="radio" name="treatment" checked={treatment === item.name} disabled={!!busy} onChange={() => setTreatment(item.name)}/>
            <strong>{item.name}</strong><p>{item.direction}</p><small>{item.rationale}</small>
          </label>)}
        </fieldset>
        <h2>Editing prompt</h2>
        <textarea className="prompt" rows={12} aria-label="English image-editing prompt" disabled={!!busy || promptTreatment !== treatment}
          placeholder="Generate a production prompt from the selected direction." value={promptTreatment === treatment ? prompt : ""} onChange={event => setPrompt(event.target.value)} maxLength={20000}/>
        <div className="actions">
          <button className="primary" disabled={!!busy || promptReady} onClick={() => updatePrompt(false)}><Icon kind="spark"/> Generate prompt</button>
          <button className="secondary" disabled={!!busy || !promptReady || !prompt.trim()} onClick={() => updatePrompt(true)}>Save revision</button>
          <button className="secondary" disabled={!promptReady || !prompt.trim()} onClick={download}>Download prompt</button>
        </div>
      </section>}
    </main>
  </>;
}
