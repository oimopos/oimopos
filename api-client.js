(function createAshkanaApi(global) {
  class ApiError extends Error {
    constructor(message, status = 0, details = null) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.details = details;
    }
  }

  const protocol = location.protocol === "https:" ? "https:" : "http:";
  const hostname = location.hostname || "127.0.0.1";
  const candidates = location.protocol.startsWith("http")
    ? [`${location.origin}/api/v1`, `${protocol}//${hostname}:8001/api/v1`]
    : [`http://127.0.0.1:8001/api/v1`];
  let activeBase = sessionStorage.getItem("ashkana-api-base-v1") || "";
  const pageName = location.pathname.split("/").pop() || "";
  let clientMode = ["index.html", "pos"].includes(pageName) || new URLSearchParams(location.search).get("mode") === "pos" ? "pos" : "admin";

  async function parseResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) {
      const detail = body?.detail;
      const message = typeof detail === "string" ? detail : detail?.message || `Ошибка сервера (${response.status})`;
      throw new ApiError(message, response.status, detail);
    }
    return body;
  }

  async function request(path, options = {}) {
    const bases = activeBase ? [activeBase, ...candidates.filter((base) => base !== activeBase)] : candidates;
    let lastError = null;
    for (const base of bases) {
      try {
        const response = await fetch(`${base}${path}`, {
          credentials: "include",
          headers: { "Content-Type": "application/json", "X-Ashkana-Client": clientMode, ...(options.headers || {}) },
          ...options,
        });
        const contentType = response.headers.get("content-type") || "";
        if (response.status === 404 && !contentType.includes("application/json") && base !== bases[bases.length - 1]) continue;
        const body = await parseResponse(response);
        activeBase = base;
        sessionStorage.setItem("ashkana-api-base-v1", base);
        return body;
      } catch (error) {
        if (error instanceof ApiError) throw error;
        lastError = error;
      }
    }
    throw new ApiError("Сервер Oimo недоступен. Запустите Docker и обновите страницу.", 0, lastError?.message);
  }

  global.AshkanaApi = {
    ApiError,
    setClientMode: (mode) => { clientMode = mode === "pos" ? "pos" : "admin"; },
    login: (login, password, registerId = null) => request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ login, password, ...(registerId ? { register_id: Number(registerId) } : {}) }),
    }),
    me: () => request("/auth/me"),
    logout: () => request("/auth/logout", { method: "POST", body: "{}" }),
    workspace: () => request("/workspace"),
    action: (action, payload = {}) => request("/workspace/actions", { method: "POST", body: JSON.stringify({ action, payload }) }),
    auditEvents: (limit = 100) => request(`/audit-events?limit=${encodeURIComponent(limit)}`),
    employees: () => request("/employees"),
    revealEmployeePin: (id) => request(`/employees/${encodeURIComponent(id)}/pin/reveal`, { method: "POST", body: "{}" }),
    createEmployee: (payload) => request("/employees", { method: "POST", body: JSON.stringify(payload) }),
    updateEmployee: (employeeId, payload) => request(`/employees/${encodeURIComponent(employeeId)}`, { method: "PUT", body: JSON.stringify(payload) }),
    posRegisters: () => request("/pos/registers"),
    createPosRegister: (payload) => request("/pos/registers", { method: "POST", body: JSON.stringify(payload) }),
    updatePosRegister: (registerId, payload) => request(`/pos/registers/${encodeURIComponent(registerId)}`, { method: "PUT", body: JSON.stringify(payload) }),
    logoutPosRegister: (registerId) => request(`/pos/registers/${encodeURIComponent(registerId)}/logout`, { method: "POST", body: "{}" }),
    posOperators: () => request("/pos/operators"),
    posOperator: () => request("/pos/operator"),
    productionContext: (branchId) => request(`/production/context?branch_id=${encodeURIComponent(branchId)}`),
    posProductionContext: () => request("/pos/production/context"),
    posServingSurpluses: () => request("/pos/serving/surpluses"),
    posServingWriteoffs: () => request("/pos/serving/writeoffs"),
    posReceiving: () => request("/pos/receiving"),
    posSupplyContext: () => request("/pos/supplies/context"),
    unlockPos: (pin) => request("/pos/unlock", { method: "POST", body: JSON.stringify({ pin }) }),
    lockPos: () => request("/pos/lock", { method: "POST", body: "{}" }),
    salesReport: (params) => request(`/pos/sales-report?${new URLSearchParams(params)}`),
    posShifts: (limit = 200) => request(`/pos/shifts?limit=${encodeURIComponent(limit)}`),
    openPosShift: (openingCash) => request("/pos/shifts/open", { method: "POST", body: JSON.stringify({ opening_cash: openingCash }) }),
    closingShiftStock: () => request("/pos/shifts/closing-stock"),
    closePosShift: (closingCash, stock = {}) => request("/pos/shifts/close", { method: "POST", body: JSON.stringify({ closing_cash: closingCash, ...stock }) }),
    plans: () => request("/platform/plans"),
    updatePlan: (code, payload) => request(`/platform/plans/${encodeURIComponent(code)}`, { method: "PUT", body: JSON.stringify(payload) }),
    tenants: () => request("/platform/tenants"),
    createTenant: (payload) => request("/platform/tenants", { method: "POST", body: JSON.stringify(payload) }),
    updateTenant: (tenantId, payload) => request(`/platform/tenants/${encodeURIComponent(tenantId)}`, { method: "PUT", body: JSON.stringify(payload) }),
    updateTenantOwner: (tenantId, payload) => request(`/platform/tenants/${encodeURIComponent(tenantId)}/owner-access`, { method: "PUT", body: JSON.stringify(payload) }),
    platformEvents: (limit = 100) => request(`/platform/events?limit=${encodeURIComponent(limit)}`),
    clearEndpoint: () => { activeBase = ""; sessionStorage.removeItem("ashkana-api-base-v1"); },
  };
})(window);
