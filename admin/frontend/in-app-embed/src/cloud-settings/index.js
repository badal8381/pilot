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

// One sheet shared by every instance; adopting it costs nothing per element.
const sheet = new CSSStyleSheet();
sheet.replaceSync(styleText);

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
