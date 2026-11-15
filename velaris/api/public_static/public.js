"use strict";
// One script for every public page. Server text only ever reaches the DOM as text nodes (never parsed as markup).
// It sets no cookie, sends no credentials, keeps nothing in browser storage and prints nothing: link tokens live only in the address bar.
(function () {
  const main = document.querySelector("main"), app = document.getElementById("app");
  const page = main.dataset.page, ident = location.pathname.split("/").filter(Boolean)[1] || "";
  const MAX_BODY = 2 * 1024 * 1024 - 8192;

  function el(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) { if (v === true) e.setAttribute(k, ""); else if (v !== false && v != null) e.setAttribute(k, v); }
    for (const k of kids) e.append(k);
    return e;
  }
  const show = (...nodes) => { app.replaceChildren(...nodes); main.focus(); };
  const notFound = () => show(el("h1", {}, "Not available"), el("p", { role: "alert" }, "This link is not valid or has expired."));
  const broken = (e) => show(el("h1", {}, "Something went wrong"), el("p", { role: "alert" }, e.message));
  function api(method, path, body) {
    return fetch(path, { method, credentials: "omit", cache: "no-store", referrerPolicy: "no-referrer",
      headers: body === undefined ? {} : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) })
      .then(async (r) => {
        let j = {};
        try { j = await r.json(); } catch (e) { j = {}; }
        if (r.ok && j.result) return j.result;
        const err = (j && j.error) || {};
        throw { status: r.status, code: err.code || "error", message: err.message || "Something went wrong. Please try again.", extra: j.result };
      }, () => { throw { status: 0, code: "network", message: "Could not reach the server. Check your connection and try again." }; });
  }
  const live = el("p", { role: "status", "aria-live": "polite" });
  const alertBox = el("p", { role: "alert" });
  function say(text) { alertBox.textContent = ""; live.textContent = text; }
  function fail(e) { live.textContent = ""; alertBox.textContent = e.message; alertBox.focus && alertBox.setAttribute("tabindex", "-1"); alertBox.focus(); }
  function field(id, label, input, hint) {
    return el("div", {}, el("label", { for: id }, label, hint ? el("span", { class: "hint" }, " " + hint) : ""), input,
      el("p", { class: "field-error", id: id + "-err", hidden: true }));
  }
  function setError(name, text) {
    const p = document.getElementById("f-" + name + "-err"), i = document.getElementById("f-" + name);
    if (!p) return;
    p.textContent = text; p.hidden = false;
    if (i) { i.setAttribute("aria-invalid", "true"); i.setAttribute("aria-describedby", p.id); }
  }
  function clearErrors(form) {
    form.querySelectorAll(".field-error").forEach((p) => { p.hidden = true; p.textContent = ""; });
    form.querySelectorAll("[aria-invalid]").forEach((i) => i.removeAttribute("aria-invalid"));
  }
  function confirmDialog(text) { return window.confirm(text); }

  // ---- careers: apply -------------------------------------------------------------------------------------------------
  function solve(ch) {
    return new Promise((resolve, reject) => {
      const w = new Worker("/static/pow-worker.js");
      w.onmessage = (ev) => { w.terminate(); ev.data.error ? reject({ message: "The security check could not be completed. Please try again." }) : resolve(ev.data.n); };
      w.onerror = () => { w.terminate(); reject({ message: "Your browser could not run the security check." }); };
      w.postMessage({ salt: ch.salt, bits: ch.bits });
    });
  }
  function readB64(file) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result).split(",", 2)[1] || "");
      r.onerror = () => reject({ message: "That file could not be read." });
      r.readAsDataURL(file);
    });
  }
  async function apply() {
    let f;
    try { f = await api("GET", "/careers/forms/" + ident); } catch (e) { return e.status === 404 ? notFound() : broken(e); }
    document.title = f.title;
    const form = el("form", { novalidate: true });
    let fileField = null;
    for (const d of f.fields) {
      const id = "f-" + d.name, req = d.required ? { required: true, "aria-required": "true" } : {};
      let input;
      if (d.type === "longtext") input = el("textarea", { id, name: d.name, rows: 5, maxlength: d.max_length, ...req });
      else if (d.type === "choice") input = el("select", { id, name: d.name, ...req }, el("option", { value: "" }, "Choose one"), ...d.choices.map((c) => el("option", { value: c }, c)));
      else if (d.type === "checkbox") { input = el("input", { id, name: d.name, type: "checkbox" }); form.append(el("div", {}, el("label", { class: "check", for: id }, input, d.label), el("p", { class: "field-error", id: id + "-err", hidden: true }))); continue; }
      else if (d.type === "file") { input = el("input", { id, name: d.name, type: "file", accept: f.file_rules.allowed.map((x) => "." + x).join(","), ...req }); fileField = input; }
      else input = el("input", { id, name: d.name, type: { email: "email", phone: "tel", number: "number", url: "url" }[d.type] || "text", maxlength: d.max_length, min: d.min, max: d.max, autocomplete: d.type === "email" ? "email" : d.type === "phone" ? "tel" : "off", ...req });
      form.append(field(id, d.label + (d.required ? "" : " (optional)"), input, d.type === "file" ? "PDF, DOCX or TXT, up to " + Math.floor(f.file_rules.max_bytes / 1048576 * 10) / 10 + " MB" : ""));
    }
    const consent = el("input", { id: "f-consent_given", name: "consent_given", type: "checkbox", required: true, "aria-required": "true" });
    form.append(el("h2", {}, "How we use your data"), el("div", { class: "notice", id: "consent-text", tabindex: "0" }, f.consent_text),
      el("p", {}, "We keep your application for " + f.retention_days + " days. You can withdraw at any time from your status page."),
      el("div", {}, el("label", { class: "check", for: "f-consent_given" }, consent, "I have read the notice above and agree to this use of my data."), el("p", { class: "field-error", id: "f-consent_given-err", hidden: true })));
    let pool = null;
    if (f.talent_pool_offer) { pool = el("input", { id: "f-talent_pool", type: "checkbox" }); form.append(el("label", { class: "check", for: "f-talent_pool" }, pool, "Optional: keep me in the talent pool for future roles.")); }
    const btn = el("button", { type: "submit" }, "Submit application");
    form.append(btn, alertBox, live);
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault(); clearErrors(form); alertBox.textContent = "";
      if (!consent.checked) { setError("consent_given", "Please tick the box to agree before submitting."); consent.focus(); return; }
      const answers = { consent_given: true };
      if (pool) answers.talent_pool = pool.checked;
      for (const d of f.fields) {
        if (d.type === "file") continue;
        const i = document.getElementById("f-" + d.name);
        if (d.type === "checkbox") answers[d.name] = i.checked;
        else if (i.value !== "") answers[d.name] = d.type === "number" ? Number(i.value) : i.value;
      }
      btn.disabled = true;
      try {
        const body = { answers, consent_version: f.consent_version };
        const file = fileField && fileField.files[0];
        if (file) {
          if (file.size > f.file_rules.max_bytes) throw { message: "That file is too large." };
          body.file_name = file.name; body.file_base64 = await readB64(file);
        }
        say("Running a short security check. This can take a few seconds.");
        const ch = (await api("GET", "/careers/challenge/" + ident)).challenge;
        body.pow_solution = { salt: ch.salt, bits: ch.bits, expires: ch.expires, signature: ch.signature, n: await solve(ch) };
        if (JSON.stringify(body).length > MAX_BODY) throw { message: "That file is too large to send." };
        say("Sending your application.");
        const r = await api("POST", "/careers/apply/" + ident, body);
        show(el("h1", {}, "Application received"), el("p", {}, r.message || "Thank you."), el("p", {}, "Your reference: ", el("strong", {}, r.reference || "")),
          el("p", {}, "Keep this reference. If you were sent a status link, you can use it to follow progress or withdraw."));
      } catch (e) {
        if (e.extra && e.extra.errors) { for (const [k, v] of Object.entries(e.extra.errors)) setError(k, v); }
        fail(e.code === "invalid_input" ? { message: "Some answers need fixing. See the messages next to each field." } : e);
        btn.disabled = false;
      }
    });
    show(el("h1", {}, f.title), form);
  }

  // ---- careers: status (a status link cannot withdraw: the withdraw link is a separate token) and withdraw ---------------------
  async function status() {
    let r;
    try { r = await api("GET", "/careers/status/" + ident); } catch (e) { return e.status === 404 ? notFound() : broken(e); }
    show(el("h1", {}, "Your application"), el("p", {}, "Progress: ", el("strong", {}, r.progress)), el("p", {}, "Last updated: " + r.updated));
  }
  function withdraw() {
    const btn = el("button", { type: "button" }, "Withdraw my application and consent");
    btn.addEventListener("click", async () => {
      if (!confirmDialog("Withdraw your application and your consent? A recruiter will process this.")) return;
      btn.disabled = true;
      try { await api("POST", "/careers/withdraw/" + ident, {}); show(el("h1", {}, "Withdrawal requested"), el("p", { role: "status" }, "We have recorded your request. A recruiter will process it.")); }
      catch (e) { if (e.status === 404) return notFound(); btn.disabled = false; fail(e); }
    });
    show(el("h1", {}, "Withdraw your application"), el("p", {}, "This withdraws your consent to us holding your data. It cannot be undone from this page."), btn, alertBox);
  }

  // ---- interview scheduling ------------------------------------------------------------------------------------------------
  async function schedule() {
    let r;
    try { r = await api("GET", "/schedule/" + ident + "/slots"); } catch (e) { return e.status === 404 ? notFound() : broken(e); }
    if (!r.starts.length) return show(el("h1", {}, r.title), el("p", {}, "No times are free on this link right now. Please contact the recruiter."), el("button", { type: "button", class: "secondary", id: "cancel" }, "Cancel my booking"));
    const set = el("fieldset", {}, el("legend", {}, "Choose a time (" + r.duration_min + " minutes, India Standard Time)"));
    r.slots.forEach((s, i) => set.append(el("label", { class: "slot", for: "s" + i }, el("input", { type: "radio", name: "start", id: "s" + i, value: String(r.starts[i]), required: true }), s)));
    const pick = el("button", { type: "submit" }, "Confirm this time"), cancel = el("button", { type: "button", class: "secondary" }, "Cancel my booking");
    const form = el("form", {}, set, pick, cancel, alertBox, live);
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const c = form.querySelector("input:checked"); if (!c) { fail({ message: "Choose a time first." }); return; }
      pick.disabled = true;
      try { const o = await api("POST", "/schedule/" + ident + "/pick", { start: Number(c.value) }); say("Booked for " + o.confirmed_for + ". You can come back to this link to move or cancel."); }
      catch (e) { if (e.status === 404) return notFound(); fail(e); } finally { pick.disabled = false; }
    });
    cancel.addEventListener("click", async () => {
      if (!confirmDialog("Cancel your booking?")) return;
      try { await api("POST", "/schedule/" + ident + "/cancel", {}); say("Your booking is cancelled."); } catch (e) { fail(e); }
    });
    show(el("h1", {}, r.title), form);
  }

  // ---- e-sign ceremony -----------------------------------------------------------------------------------------------------
  function sign() {
    const email = el("input", { id: "email", type: "email", required: true, autocomplete: "email", "aria-required": "true" });
    const go = el("button", { type: "submit" }, "Open the document");
    const form = el("form", {}, field("email", "Your e-mail address", email, "(the one this request was sent to)"), go, alertBox, live);
    const step = (p, b) => api("POST", "/sign/" + ident + "/" + p, { email: email.value.trim(), ...b });
    const bad = (e) => { if (e.status === 404) return notFound(); fail(e); };
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault(); go.disabled = true;
      try { const d = await step("open", {}); document.title = d.title; ceremony(d); } catch (e) { bad(e); } finally { go.disabled = false; }
    });
    function ceremony(d) {
      const out = el("div", {}, el("h1", {}, d.title), el("p", {}, "You are signing as ", el("strong", {}, d.signer), "."),
        el("p", {}, "Document fingerprint (SHA-256): ", el("code", {}, d.document_sha256)), el("p", {}, "This request expires " + d.expires_at + "."));
      const code = el("input", { id: "code", inputmode: "numeric", autocomplete: "one-time-code", maxlength: 6, pattern: "[0-9]{6}" });
      const consent = el("input", { type: "checkbox", id: "agree" }), name = el("input", { id: "typed", autocomplete: "name" });
      const sendOtp = el("button", { type: "button", class: "secondary" }, "Send me a code"), verify = el("button", { type: "button" }, "Verify code");
      const doSign = el("button", { type: "button" }, "Sign"), decline = el("button", { type: "button", class: "secondary" }, "Decline to sign");
      const run = (btn, fn) => async () => { btn.disabled = true; try { await fn(); } catch (e) { bad(e); } finally { btn.disabled = false; } };
      if (d.otp_required) out.append(el("h2", {}, "Step 1: verify it is you"), sendOtp, field("code", "One-time code", code, "(6 digits)"), verify);
      out.append(el("h2", {}, d.otp_required ? "Step 2: consent to sign electronically" : "Step 1: consent to sign electronically"), el("div", { class: "notice" }, d.consent_text),
        el("label", { class: "check", for: "agree" }, consent, "I agree to use electronic records and signatures."),
        el("h2", {}, "Sign"), el("p", {}, d.intent_statement), field("typed", "Type your full name exactly as shown above", name), doSign, decline, alertBox, live);
      sendOtp.addEventListener("click", run(sendOtp, async () => { await step("otp/request", {}); say("A code was sent. It expires soon."); }));
      verify.addEventListener("click", run(verify, async () => { await step("otp/verify", { code: code.value.trim() }); say("Code verified."); }));
      doSign.addEventListener("click", run(doSign, async () => {
        if (!consent.checked) throw { message: "Please agree to electronic signing first." };
        await step("consent", { consent_text_version: d.consent_text_version });
        await step("sign", { typed_name: name.value });
        show(el("h1", {}, "Signed"), el("p", { role: "status" }, "Thank you. Your signature was recorded."));
      }));
      decline.addEventListener("click", run(decline, async () => {
        if (!confirmDialog("Decline to sign? This closes the whole request for everyone.")) return;
        await step("decline", {});
        show(el("h1", {}, "Declined"), el("p", { role: "status" }, "You declined. The request is closed."));
      }));
      show(out);
    }
    show(el("h1", {}, "Sign a document"), el("p", {}, "Confirm your e-mail address to open the document."), form);
  }

  // ---- interview participant -----------------------------------------------------------------------------------------------
  function interview() {
    const NOTICE = "v1";
    const scopes = [["events", "Activity during the session (joining, leaving, switching away from this page)"]];
    const boxes = scopes.map(([v, t], i) => el("label", { class: "check", for: "sc" + i }, el("input", { type: "checkbox", id: "sc" + i, value: v, checked: true }), t));
    const join = el("button", { type: "submit" }, "Agree and join"), withdraw = el("button", { type: "button", class: "secondary" }, "Withdraw consent and leave");
    const form = el("form", {}, el("div", { class: "notice" }, "This interview keeps a factual log of the activity ticked below, for a human reviewer. Nothing is scored by software. You can withdraw at any time on this page. Notice " + NOTICE + "."),
      el("fieldset", {}, el("legend", {}, "What may be recorded"), ...boxes), join, withdraw, alertBox, live);
    let on = false;
    const ev = (type, data) => api("POST", "/interview/" + ident + "/events", data ? { type, data } : { type }).catch(() => null);
    form.addEventListener("submit", async (e) => {
      e.preventDefault(); const chosen = boxes.map((b) => b.querySelector("input")).filter((i) => i.checked).map((i) => i.value);
      if (!chosen.length) { fail({ message: "Tick at least one item, or choose Withdraw." }); return; }
      join.disabled = true;
      try { await api("POST", "/interview/" + ident + "/consent", { scopes: chosen, notice_version: NOTICE }); await api("POST", "/interview/" + ident + "/events", { type: "join" }); on = true; say("You have joined. Keep this page open during the interview."); }
      catch (err) { if (err.status === 404) return notFound(); join.disabled = false; fail(err); }
    });
    document.addEventListener("visibilitychange", () => { if (on) ev("visibility", { state: document.visibilityState }); });
    addEventListener("pagehide", () => { if (on) fetch("/interview/" + ident + "/events", { method: "POST", keepalive: true, credentials: "omit", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: "leave" }) }).catch(() => null); });
    withdraw.addEventListener("click", async () => {
      if (!confirmDialog("Withdraw your consent and leave this interview?")) return;
      try { on = false; await api("POST", "/interview/" + ident + "/withdraw", {}); show(el("h1", {}, "Consent withdrawn"), el("p", { role: "status" }, "Your consent is withdrawn and recording has stopped.")); } catch (e) { bad404(e); }
    });
    const bad404 = (e) => (e.status === 404 ? notFound() : fail(e));
    show(el("h1", {}, "Interview"), form);
  }

  ({ apply, status, withdraw, schedule, sign, interview })[page]();
})();
