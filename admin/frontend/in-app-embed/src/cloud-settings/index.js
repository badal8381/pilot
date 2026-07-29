/* Cloud Settings in-app embed entry.
 *
 * Pilot owns the whole dialog, registered as a shadow-DOM custom element so
 * Tailwind's reset and frappe-ui's styles cannot reach Desk (and vice versa).
 * `frappe.cloudSettings.show(context)` is the entire contract Desk calls.
 */
import { defineCustomElement, h } from "vue";
import styleText from "./tailwind.css?inline";
import CloudSettings from "./CloudSettings.vue";

const TAG = "fc-cloud-settings";

// frappe-ui declares every design token (colors, radius, elevation, focus) on
// `:root` and flips the dark set on `[data-theme=dark]`. Inside a shadow root
// neither selector matches — `:root` is the document, not the host — so the
// embed would inherit whatever tokens Desk happens to expose and silently drop
// the rest (radius has none on older Desk).
const scopedStyleText = styleText
  .replace(/:root\b/g, ":host")
  .replace(/\[data-theme=(["']?)dark\1\]/g, ":host([data-theme=dark])");

// One sheet shared by every instance; adopting it costs nothing per element.
const sheet = new CSSStyleSheet();
sheet.replaceSync(scopedStyleText);

const CloudSettingsElement = defineCustomElement({
  props: { context: Object, open: Boolean },
  emits: ["close"],
  shadowRoot: true,
  configureApp(app) {
    // Templates compile `__("…")` to `_ctx.__`, so it must be a global property.
    app.config.globalProperties.__ = window.__;
  },
  setup(props, { emit }) {
    return () =>
      h(CloudSettings, {
        context: props.context,
        open: props.open,
        onClose: () => emit("close"),
      });
  },
});

class CloudSettingsHost extends CloudSettingsElement {
  connectedCallback() {
    super.connectedCallback();
    const root = this.shadowRoot;
    if (!root.adoptedStyleSheets.includes(sheet)) {
      root.adoptedStyleSheets = [...root.adoptedStyleSheets, sheet];
    }
    // Desk flips its theme on <html data-theme>; mirror it onto the host so the
    // shadow tree's `:host([data-theme=dark])` tokens follow it.
    this.syncTheme();
    this.themeObserver = new MutationObserver(() => this.syncTheme());
    this.themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
  }

  disconnectedCallback() {
    super.disconnectedCallback?.();
    this.themeObserver?.disconnect();
  }

  syncTheme() {
    const theme = document.documentElement.getAttribute("data-theme") || "light";
    this.setAttribute("data-theme", theme);
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, CloudSettingsHost);

frappe.cloudSettings = {
  show(context) {
    let host = document.querySelector(TAG);
    if (!host) {
      host = document.createElement(TAG);
      // Kept in the DOM so reopening is instant; `open` drives its state.
      host.addEventListener("close", () => {
        host.open = false;
      });
      document.body.appendChild(host);
    }
    host.context = context || {};
    host.open = true;
  },
};
