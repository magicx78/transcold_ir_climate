/* Transcold IR Climate - sidebar panel (vanilla web component, no build step). */

const STRINGS = {
  de: {
    subtitle: "IR-Klimageräte, Protokolle und Code-Bibliothek verwalten",
    tab_devices: "Geräte",
    tab_library: "Bibliothek",
    tab_import: "Import",
    add_device: "+ Gerät hinzufügen",
    no_devices: "Noch keine Geräte konfiguriert.",
    target: "Sender",
    protocol: "Protokoll",
    state: "Status",
    not_loaded: "nicht geladen",
    builtin: "eingebaut",
    imported: "importiert",
    custom_py: "Eigenes Protokoll (Python)",
    temp_range: "Temperatur",
    modes: "Modi",
    fans: "Lüfter",
    delete: "Löschen",
    delete_confirm: "Datei wirklich löschen? Geräte, die dieses Protokoll nutzen, funktionieren danach nicht mehr.",
    drop_title: "SmartIR-JSON oder Protokoll-Datei (.py) hier ablegen",
    drop_hint: "Dateien landen update-sicher in /config/transcold_ir/ und erscheinen sofort im Protokoll-Dropdown neuer Geräte.",
    browse: "Durchsuchen…",
    library_hint: "SmartIR-Code-Sets für hunderte Klimageräte findest du unter",
    import_ok: "importiert - als Protokoll wählbar:",
    import_failed: "Import fehlgeschlagen",
    invalid_file: "Ungültige Datei",
    loading: "Lade…",
    error_loading: "Fehler beim Laden",
    no_library: "Noch nichts importiert. Ziehe eine SmartIR-JSON auf den Import-Tab.",
  },
  en: {
    subtitle: "Manage IR climate devices, protocols and the code library",
    tab_devices: "Devices",
    tab_library: "Library",
    tab_import: "Import",
    add_device: "+ Add device",
    no_devices: "No devices configured yet.",
    target: "Transmitter",
    protocol: "Protocol",
    state: "State",
    not_loaded: "not loaded",
    builtin: "built-in",
    imported: "imported",
    custom_py: "Custom protocol (Python)",
    temp_range: "Temperature",
    modes: "Modes",
    fans: "Fan",
    delete: "Delete",
    delete_confirm: "Really delete this file? Devices using this protocol will stop working.",
    drop_title: "Drop a SmartIR JSON or protocol file (.py) here",
    drop_hint: "Files are stored update-safe in /config/transcold_ir/ and appear immediately in the protocol dropdown for new devices.",
    browse: "Browse…",
    library_hint: "SmartIR code sets for hundreds of AC units are available at",
    import_ok: "imported - selectable as protocol:",
    import_failed: "Import failed",
    invalid_file: "Invalid file",
    loading: "Loading…",
    error_loading: "Failed to load",
    no_library: "Nothing imported yet. Drop a SmartIR JSON onto the Import tab.",
  },
};

class TranscoldIrPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = "devices";
    this._built = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) {
      this._built = true;
      this._t = STRINGS[(hass.language || "en").startsWith("de") ? "de" : "en"];
      this._render();
      this._refresh();
    }
  }

  set panel(panel) {
    this._panel = panel;
  }

  _render() {
    const t = this._t;
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          height: 100%;
          overflow-y: auto;
          background: var(--primary-background-color);
          color: var(--primary-text-color);
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
        }
        .wrap { max-width: 860px; margin: 0 auto; padding: 16px; }
        header h1 {
          font-size: 24px; font-weight: 400; margin: 8px 0 2px;
          display: flex; align-items: center; gap: 10px;
        }
        header p { margin: 0 0 16px; color: var(--secondary-text-color); font-size: 14px; }
        nav {
          display: flex; gap: 4px; border-bottom: 1px solid var(--divider-color);
          margin-bottom: 16px;
        }
        nav button {
          background: none; border: none; cursor: pointer; padding: 12px 18px;
          font-size: 14px; font-weight: 500; letter-spacing: .5px;
          color: var(--secondary-text-color); text-transform: uppercase;
          border-bottom: 2px solid transparent;
        }
        nav button.active {
          color: var(--primary-color); border-bottom-color: var(--primary-color);
        }
        .card {
          background: var(--card-background-color);
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.12));
          padding: 14px 16px; margin-bottom: 10px;
        }
        .card .title { font-weight: 500; display: flex; align-items: center; gap: 8px; }
        .card .meta { color: var(--secondary-text-color); font-size: 13px; margin-top: 4px; }
        .badge {
          font-size: 11px; padding: 2px 8px; border-radius: 10px;
          background: var(--primary-color); color: var(--text-primary-color, #fff);
        }
        .badge.gray { background: var(--secondary-text-color); }
        .badge.warn { background: var(--error-color, #db4437); }
        .row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
        .actions button, .primary {
          border: none; border-radius: 6px; cursor: pointer; font-size: 13px;
          padding: 8px 14px; background: var(--primary-color);
          color: var(--text-primary-color, #fff);
        }
        .actions button.danger { background: var(--error-color, #db4437); }
        .drop {
          border: 2px dashed var(--divider-color); border-radius: 12px;
          padding: 28px 20px; text-align: center; cursor: pointer;
          transition: border-color .15s, background .15s;
        }
        .drop.over {
          border-color: var(--primary-color);
          background: color-mix(in srgb, var(--primary-color) 8%, transparent);
        }
        .drop .big { font-weight: 500; margin-bottom: 6px; }
        .drop .hint { color: var(--secondary-text-color); font-size: 13px; }
        .drop button { margin-top: 12px; }
        #status { margin-top: 12px; font-size: 14px; }
        #status.ok { color: var(--success-color, #0f9d58); }
        #status.err { color: var(--error-color, #db4437); }
        .footnote { color: var(--secondary-text-color); font-size: 12px; margin-top: 16px; }
        a { color: var(--primary-color); }
        .empty { color: var(--secondary-text-color); padding: 24px 0; text-align: center; }
      </style>
      <div class="wrap">
        <header>
          <h1>Transcold IR Climate</h1>
          <p>${t.subtitle}</p>
        </header>
        <nav>
          <button data-tab="devices">${t.tab_devices}</button>
          <button data-tab="library">${t.tab_library}</button>
          <button data-tab="import">${t.tab_import}</button>
        </nav>
        <div id="content"></div>
      </div>
    `;
    this.shadowRoot.querySelectorAll("nav button").forEach((b) =>
      b.addEventListener("click", () => {
        this._tab = b.dataset.tab;
        this._refresh();
      })
    );
  }

  async _api(method, path, body) {
    return this._hass.callApi(method, `transcold_ir_climate/${path}`, body);
  }

  _setActiveTab() {
    this.shadowRoot
      .querySelectorAll("nav button")
      .forEach((b) => b.classList.toggle("active", b.dataset.tab === this._tab));
  }

  async _refresh() {
    this._setActiveTab();
    const el = this.shadowRoot.getElementById("content");
    el.innerHTML = `<div class="empty">${this._t.loading}</div>`;
    try {
      if (this._tab === "devices") await this._renderDevices(el);
      else if (this._tab === "library") await this._renderLibrary(el);
      else this._renderImport(el);
    } catch (err) {
      el.innerHTML = `<div class="empty">${this._t.error_loading}: ${err.message || err}</div>`;
    }
  }

  async _renderDevices(el) {
    const t = this._t;
    const { devices } = await this._api("GET", "devices");
    const cards = devices
      .map((d) => {
        const target = d.remote_entity || d.esphome_service || "-";
        const state =
          (d.entity_id && this._hass.states[d.entity_id]?.state) ||
          d.state ||
          "-";
        const warn = d.loaded ? "" : ` <span class="badge warn">${t.not_loaded}</span>`;
        return `
          <div class="card">
            <div class="row">
              <div>
                <div class="title">${esc(d.title)}${warn}</div>
                <div class="meta">${d.entity_id ? esc(d.entity_id) + " · " : ""}${t.state}: ${esc(state)}</div>
                <div class="meta">${t.protocol}: ${esc(d.protocol || "-")} · ${t.target}: ${esc(target)}</div>
              </div>
            </div>
          </div>`;
      })
      .join("");
    el.innerHTML = `
      ${cards || `<div class="empty">${t.no_devices}</div>`}
      <button class="primary" id="add">${t.add_device}</button>
    `;
    el.querySelector("#add").addEventListener("click", () => {
      history.pushState(null, "", "/config/integrations/dashboard/add?domain=transcold_ir_climate");
      window.dispatchEvent(new CustomEvent("location-changed"));
    });
  }

  async _renderLibrary(el) {
    const t = this._t;
    const [{ protocols }, { items }] = await Promise.all([
      this._api("GET", "protocols"),
      this._api("GET", "codesets"),
    ]);
    const fileByProtocol = {};
    items.forEach((i) => {
      if (i.protocol) fileByProtocol[i.protocol] = i.filename;
    });

    const cards = Object.values(protocols)
      .map((p) => {
        const badge = p.builtin
          ? `<span class="badge gray">${t.builtin}</span>`
          : `<span class="badge">${t.imported}</span>`;
        const file = fileByProtocol[p.name] || p.source;
        const del = !p.builtin && file
          ? `<div class="actions"><button class="danger" data-file="${esc(file)}">${t.delete}</button></div>`
          : "";
        return `
          <div class="card">
            <div class="row">
              <div>
                <div class="title">${esc(p.description || p.name)} ${badge}</div>
                <div class="meta">${t.protocol}: <code>${esc(p.name)}</code>${file ? " · " + esc(file) : ""}</div>
                <div class="meta">${t.temp_range}: ${p.min_temp}-${p.max_temp} °C · ${t.modes}: ${p.hvac_modes.join(", ")} · ${t.fans}: ${p.fan_modes.join(", ")}</div>
              </div>
              ${del}
            </div>
          </div>`;
      })
      .join("");

    const pyFiles = items
      .filter((i) => i.type === "python")
      .map(
        (i) => `
          <div class="card">
            <div class="row">
              <div>
                <div class="title">${esc(i.filename)} <span class="badge">${t.custom_py}</span></div>
              </div>
              <div class="actions"><button class="danger" data-file="${esc(i.filename)}">${t.delete}</button></div>
            </div>
          </div>`
      )
      .join("");

    const broken = items
      .filter((i) => i.type === "smartir" && !i.valid)
      .map(
        (i) => `
          <div class="card">
            <div class="row">
              <div>
                <div class="title">${esc(i.filename)} <span class="badge warn">${t.invalid_file}</span></div>
                <div class="meta">${esc(i.error || "")}</div>
              </div>
              <div class="actions"><button class="danger" data-file="${esc(i.filename)}">${t.delete}</button></div>
            </div>
          </div>`
      )
      .join("");

    el.innerHTML = `
      ${cards + pyFiles + broken || `<div class="empty">${t.no_library}</div>`}
      <div class="footnote">${t.library_hint}
        <a href="https://github.com/smartHomeHub/SmartIR/tree/master/codes/climate" target="_blank" rel="noopener">github.com/smartHomeHub/SmartIR</a>
      </div>
    `;
    el.querySelectorAll("button.danger").forEach((b) =>
      b.addEventListener("click", async () => {
        if (!confirm(t.delete_confirm)) return;
        await this._api("DELETE", `codesets/${encodeURIComponent(b.dataset.file)}`);
        this._refresh();
      })
    );
  }

  _renderImport(el) {
    const t = this._t;
    el.innerHTML = `
      <div class="drop" id="drop">
        <div class="big">⊕ ${t.drop_title}</div>
        <div class="hint">${t.drop_hint}</div>
        <button class="primary" id="browse">${t.browse}</button>
        <input type="file" id="file" accept=".json,.py" multiple hidden />
      </div>
      <div id="status"></div>
    `;
    const drop = el.querySelector("#drop");
    const input = el.querySelector("#file");

    el.querySelector("#browse").addEventListener("click", (e) => {
      e.stopPropagation();
      input.click();
    });
    drop.addEventListener("click", () => input.click());
    input.addEventListener("change", () => this._importFiles(input.files));

    ["dragenter", "dragover"].forEach((ev) =>
      drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.add("over");
      })
    );
    ["dragleave", "drop"].forEach((ev) =>
      drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.remove("over");
      })
    );
    drop.addEventListener("drop", (e) => this._importFiles(e.dataTransfer.files));
  }

  async _importFiles(files) {
    const t = this._t;
    const status = this.shadowRoot.getElementById("status");
    const lines = [];
    for (const file of files) {
      try {
        const content = await file.text();
        const result = await this._api("POST", "codesets", {
          filename: file.name,
          content,
        });
        const proto = result.protocol ? ` <code>${esc(result.protocol)}</code>` : "";
        lines.push(`✔ ${esc(file.name)} ${t.import_ok}${proto}`);
        status.className = "ok";
      } catch (err) {
        const detail = err?.body?.detail || err?.body?.error || err.message || err;
        lines.push(`✘ ${esc(file.name)}: ${t.import_failed} (${esc(String(detail))})`);
        status.className = "err";
      }
    }
    status.innerHTML = lines.join("<br>");
  }
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

customElements.define("transcold-ir-panel", TranscoldIrPanel);
