import { reactive } from "vue";
import * as api from "./api";

const POLL_INTERVAL = 2500;
const MAX_WAIT = 3 * 60 * 1000; // give up watching a task after 3 minutes

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Poll a bench task: "success" | "failed" | "timeout" | "gone" | "error" |
// "cancelled". "timeout"/"gone" may still be running, so don't claim an outcome.
export async function waitForTask(taskId, isCancelled = () => false) {
  const deadline = Date.now() + MAX_WAIT;
  while (!isCancelled()) {
    let task;
    try {
      task = await api.getTask(taskId);
    } catch {
      return "error";
    }
    const status = task && task.status;
    if (!status) return "gone";
    // Only these are terminal; queued/pending states are still in flight.
    if (!["success", "failed", "killed"].includes(status)) {
      if (Date.now() > deadline) return "timeout";
      await sleep(POLL_INTERVAL);
      continue;
    }
    const succeeded =
      status === "success" && (task.exit_code === 0 || task.exit_code == null);
    return succeeded ? "success" : "failed";
  }
  return "cancelled";
}

// Shared across panels; each section loads lazily and refreshes itself.
export function createStore(context) {
  const state = reactive({
    context: context || {},
    billing: null,
    billingError: "",
    marketplace: null,
    marketplaceError: "",
    domains: null,
    domainsError: "",
  });

  async function loadBilling(force = false) {
    state.billingError = "";
    if (state.billing && !force) return;
    try {
      state.billing = await api.getBilling();
    } catch (exception) {
      state.billingError = api.getErrorMessage(exception);
    }
  }

  async function loadMarketplace(force = false) {
    state.marketplaceError = "";
    if (state.marketplace && !force) return;
    try {
      state.marketplace = await api.getMarketplaceApps();
    } catch (exception) {
      state.marketplaceError = api.getErrorMessage(exception);
    }
  }

  async function loadDomains(force = false) {
    state.domainsError = "";
    if (state.domains && !force) return;
    try {
      state.domains = await api.getDomains();
    } catch (exception) {
      state.domainsError = api.getErrorMessage(exception);
    }
  }

  return {
    state,
    api,
    loadBilling,
    loadMarketplace,
    loadDomains,
  };
}
