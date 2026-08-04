import "@testing-library/jest-dom";

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
  onopen: ((this: MockEventSource, ev: Event) => any) | null = null;
  onmessage: ((this: MockEventSource, ev: MessageEvent) => any) | null = null;
  onerror: ((this: MockEventSource, ev: Event) => any) | null = null;

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

(global as any).EventSource = MockEventSource;
