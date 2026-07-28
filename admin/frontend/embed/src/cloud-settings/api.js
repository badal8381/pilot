// Everything goes through desk's `frappe.call`, so the pilot token stays
// server-side and the calls are same-origin. Method names mirror
// `cloud_settings.py`, which is the versioned contract — keep them in sync.

const METHOD_PREFIX = "frappe.integrations.frappe_providers.cloud_settings";

// Errors render inline, so suppress frappe's toast and reject with its message.
function call(method, args = {}, type = "POST") {
  return new Promise((resolve, reject) => {
    const request = frappe.call({
      method: `${METHOD_PREFIX}.${method}`,
      args,
      type,
      silent: true,
      callback: (response) => resolve(response.message),
      error: (response) => reject(errorFromResponse(response)),
    });
    // frappe.call resolves/rejects its own promise too. Settle from it as well so
    // a failure frappe handles globally (session expiry) can't leave us pending
    // forever behind `silent: true`; whichever settles first wins.
    Promise.resolve(request).then(
      (response) => response && resolve(response.message),
      (exception) => reject(errorFromResponse(exception)),
    );
  });
}

// `exc_type` (the framework exception class) is how callers tell a migration
// conflict, which needs its own action, from a generic failure.
function errorFromResponse(response) {
  const error = new Error(messageFromResponse(response));
  error.excType = response?.exc_type || response?.responseJSON?.exc_type || "";
  return error;
}

export function isMigrationConflict(exception) {
  return exception?.excType === "CloudMigrationConflictError";
}

// Pull the human-readable message out of a frappe error response.
function messageFromResponse(response) {
  const raw =
    response?._server_messages || response?.responseJSON?._server_messages;
  if (raw) {
    try {
      const messages = JSON.parse(raw)
        .map((item) => JSON.parse(item).message)
        .filter(Boolean);
      if (messages.length) return messages.join(". ").replace(/<[^>]*>/g, "");
    } catch {
      // fall through to the generic message
    }
  }
  const exception = response?.exc_type || response?.responseJSON?.exc_type;
  const status = response?.status || response?.httpStatus;
  if (status === 403) return __("You don't have permission to do this.");
  if (exception) return __("{0}. Please try again.", [exception]);
  return __("Something went wrong. Please try again.");
}

export function getContext() {
  return call("get_context", {}, "GET");
}

export function getAccountUrl() {
  return call("get_account_url", {}, "GET");
}

export function getBilling() {
  return call("get_billing", {}, "GET");
}

export function getPlanOptions({ provider, region } = {}) {
  const args = {};
  if (provider) args.provider = provider;
  if (region) args.region = region;
  return call("get_plan_options", args, "GET");
}

export function changePlan(plan) {
  return call("change_plan", { plan });
}

export function getBillingProfile() {
  return call("get_billing_profile", {}, "GET");
}

export function saveBillingProfile(fields) {
  return call("save_billing_profile", fields);
}

export function removePaymentMethod(name) {
  return call("remove_payment_method", { payment_method: name });
}

export function getPaymentGateways() {
  return call("get_payment_gateways", {}, "GET");
}

export function addPaymentMethod(methodType, gateway, contact) {
  return call("add_payment_method", {
    method_type: methodType,
    gateway,
    contact,
  });
}

export function confirmPaymentMethod(payload) {
  return call("confirm_payment_method", payload);
}

export function createPaymentMethodCheckout(redirectUrl, gateway) {
  return call("create_payment_method_checkout", {
    redirect_url: redirectUrl,
    gateway,
  });
}

export function confirmPaymentMethodCheckout(reference) {
  return call("confirm_payment_method_checkout", { reference });
}

export function reconcilePaymentSetup() {
  return call("reconcile_payment_setup", {});
}

export function getMarketplaceApps() {
  return call("get_marketplace_apps", {}, "GET");
}

export function installApp(app) {
  return call("install_app", { app });
}

export function uninstallApp(app) {
  return call("uninstall_app", { app });
}

export function updateApps(apps) {
  const args = apps ? { apps: JSON.stringify(apps) } : {};
  return call("update_apps", args);
}

export function getTask(taskId) {
  return call("get_task", { task_id: taskId }, "GET");
}

export function getDomains() {
  return call("get_domains", {}, "GET");
}

export function getDomainDnsRecords(domain) {
  return call("get_domain_dns_records", { domain });
}

export function addDomain(domain) {
  return call("add_domain", { domain });
}

export function removeDomain(domain) {
  return call("remove_domain", { domain });
}

export function setPrimaryDomain(domain) {
  return call("set_primary_domain", { domain });
}

export function getErrorMessage(exception, fallback) {
  // call() rejects with an Error already carrying the server's message.
  return exception?.message || fallback || __("Something went wrong.");
}
