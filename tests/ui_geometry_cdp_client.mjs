export function createCdpClientClass({ ProbeFailure, failurePayload }) {
  return class CdpClient {
  constructor(wsUrl) {
    this.nextId = 1;
    this.pending = new Map();
    this.waiters = new Map();
    this.ws = new WebSocket(wsUrl);
    this.context = {};
  }

  async open(timeoutMs = 10000) {
    await new Promise((resolve, reject) => {
      let settled = false;
      const finish = (callback, value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        callback(value);
      };
      const websocketFailure = (stage, details = {}) => new ProbeFailure(
        "cdp_websocket_failed",
        failurePayload("cdp_websocket_failed", {
          stage,
          wsUrl: this.ws.url || "",
          ...details,
        })
      );
      const timer = setTimeout(() => {
        finish(reject, websocketFailure("CdpClient.open.timeout", { timeoutMs }));
      }, timeoutMs);
      this.ws.onopen = () => finish(resolve, undefined);
      this.ws.onerror = (error) => finish(reject, websocketFailure("CdpClient.open.error", {
        message: String(error && error.message ? error.message : error),
      }));
      this.ws.onmessage = (event) => this.onMessage(event);
      this.ws.onclose = (event) => finish(reject, websocketFailure("CdpClient.open.close", {
        code: event && event.code,
        reason: event && event.reason,
      }));
    });
    this.ws.onerror = (error) => this.rejectAll(new ProbeFailure(
      "cdp_websocket_failed",
      failurePayload("cdp_websocket_failed", {
        stage: "CdpClient.onerror",
        wsUrl: this.ws.url || "",
        message: String(error && error.message ? error.message : error),
      })
    ));
    this.ws.onclose = (event) => this.rejectAll(new ProbeFailure(
      "cdp_websocket_failed",
      failurePayload("cdp_websocket_failed", {
        stage: "CdpClient.onclose",
        wsUrl: this.ws.url || "",
        code: event && event.code,
        reason: event && event.reason,
      })
    ));
  }

  rejectAll(error) {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
    for (const waiters of this.waiters.values()) {
      for (const waiter of waiters) {
        clearTimeout(waiter.timer);
        waiter.reject(error);
      }
    }
    this.waiters.clear();
  }

  onMessage(event) {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch (error) {
      this.rejectAll(new ProbeFailure(
        "cdp_websocket_failed",
        failurePayload("cdp_websocket_failed", {
          stage: "CdpClient.onMessage.parse",
          message: `CDP JSON parse failed: ${String(error)}`,
        })
      ));
      return;
    }
    if (payload.id && this.pending.has(payload.id)) {
      const { resolve, reject, timer } = this.pending.get(payload.id);
      clearTimeout(timer);
      this.pending.delete(payload.id);
      if (payload.error) {
        reject(new Error(JSON.stringify(payload.error)));
      } else {
        resolve(payload.result || {});
      }
      return;
    }
    const waiters = this.waiters.get(payload.method) || [];
    const waiter = waiters.shift();
    if (waiter) {
      clearTimeout(waiter.timer);
      waiter.resolve(payload.params || {});
    }
  }

  send(method, params = {}, timeoutMs = 10000) {
    const id = this.nextId;
    this.nextId += 1;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new ProbeFailure("cdp_command_timeout", failurePayload("cdp_command_timeout", {
          stage: "cdp.send",
          method,
          paramsSummary: JSON.stringify(params).slice(0, 1024),
          pageUrl: this.context.url || "",
          viewport: this.context.viewport || {},
        })));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer, method, params });
      try {
        this.ws.send(JSON.stringify({ id, method, params }));
      } catch (error) {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(error);
      }
    });
  }

  waitEvent(method, timeoutMs = 10000) {
    return new Promise((resolve, reject) => {
      const waiters = this.waiters.get(method) || [];
      const waiter = {
        resolve: (value) => {
          clearTimeout(timer);
          const rows = this.waiters.get(method) || [];
          this.waiters.set(method, rows.filter((item) => item !== waiter));
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          const rows = this.waiters.get(method) || [];
          this.waiters.set(method, rows.filter((item) => item !== waiter));
          reject(error);
        },
        timer: null,
      };
      const timer = setTimeout(() => {
        const rows = this.waiters.get(method) || [];
        this.waiters.set(method, rows.filter((item) => item !== waiter));
        reject(new ProbeFailure("cdp_command_timeout", failurePayload("cdp_command_timeout", {
          stage: "cdp.waitEvent",
          event: method,
          timeoutMs,
          pageUrl: this.context.url || "",
          viewport: this.context.viewport || {},
        })));
      }, timeoutMs);
      waiter.timer = timer;
      waiters.push(waiter);
      this.waiters.set(method, waiters);
    });
  }

  close() {
    try { this.ws.close(); } catch {}
  }
}
}
