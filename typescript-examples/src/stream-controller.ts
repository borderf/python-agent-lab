import { reduceAnswer, type AnswerState, type StreamEvent } from "./stream-state.js";
import { StreamFailure } from "./stream-client.js";

export type StreamRunner<T> = (input: T, receive: (event: StreamEvent) => void, signal: AbortSignal) => Promise<void>;
type Run = { scope: string; abort: AbortController; buffer: string; timer: ReturnType<typeof setTimeout> | null; terminal: boolean };

// 每轮拥有自己的缓冲/计时器。旧轮次的finally只能清理自己的资源。
export class StreamController<T> {
  private current: Run | null = null;
  private state: AnswerState = { status: "idle" };
  constructor(private runner: StreamRunner<T>, private emit: (state: AnswerState, scope: string | null) => void,
    private flushMs = 50) {}
  private clear(run: Run) {
    if (run.timer !== null) clearTimeout(run.timer);
    run.timer = null;
    run.buffer = "";
  }
  private publish(action: Parameters<typeof reduceAnswer>[1], scope: string) {
    this.state = reduceAnswer(this.state, action);
    this.emit(this.state, scope);
  }
  private flush(run: Run) {
    const text = run.buffer;
    this.clear(run);
    if (this.current === run && text) this.publish({ type: "tokens", text }, run.scope);
  }
  dispose() {
    const run = this.current;
    this.current = null; // 先使回调失效，再通知取消。
    if (run) { this.clear(run); run.abort.abort(); }
  }
  reset(scope: string | null) {
    this.dispose();
    this.state = { status: "idle" };
    this.emit(this.state, scope);
  }
  stop() {
    const run = this.current;
    if (!run) return;
    this.flush(run);
    this.publish({ type: "stop" }, run.scope);
    this.dispose();
  }
  async start(input: T, scope: string): Promise<void> {
    this.dispose();
    const run: Run = { scope, abort: new AbortController(), buffer: "", timer: null, terminal: false };
    this.current = run;
    this.publish({ type: "start" }, scope);
    try {
      await this.runner(input, event => {
        if (this.current !== run || run.abort.signal.aborted || run.terminal) return;
        if (event.type === "token") {
          run.buffer += event.text;
          if (run.timer === null) run.timer = setTimeout(() => this.flush(run), this.flushMs);
        } else {
          this.flush(run);
          this.publish({ type: "event", event }, scope);
          run.terminal = event.type === "done" || event.type === "error";
        }
      }, run.abort.signal);
      if (this.current === run && !run.terminal) throw new StreamFailure("缺少终止事件", true);
    } catch (error) {
      if (this.current !== run) return;
      this.flush(run);
      if (run.abort.signal.aborted) this.publish({ type: "stop" }, scope);
      else this.publish({ type: "error", message: error instanceof Error ? error.message : "生成失败",
        retryable: error instanceof StreamFailure && error.retryable }, scope);
    } finally {
      this.clear(run);
      if (this.current === run) this.current = null;
    }
  }
}
