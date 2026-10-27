import "@testing-library/jest-dom/vitest";

class MockEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSED = 2;
  readyState = 0;
  url: string;
  withCredentials = false;
  onopen: ((this: MockEventSource, ev: Event) => void) | null = null;
  onmessage: ((this: MockEventSource, ev: MessageEvent) => void) | null = null;
  onerror: ((this: MockEventSource, ev: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
  }

  close() {
    this.readyState = 2;
  }

  dispatchMessage(data: string) {
    this.onmessage?.({ data } as MessageEvent);
  }
}

Object.defineProperty(globalThis, "EventSource", {
  configurable: true,
  writable: true,
  value: MockEventSource,
});
