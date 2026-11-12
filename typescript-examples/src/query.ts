export type QueryIdentity = { subjectId: string; tenantId: string; authVersion: string; indexVersion: string };
export function searchKey(identity: QueryIdentity, question: string, asOf: string): string {
  return JSON.stringify([identity.subjectId, identity.tenantId, identity.authVersion,
    identity.indexVersion, question, asOf]);
}
export type QueryState<T> =
  | { status: "idle" }
  | { status: "loading"; key: string; previous?: T }
  | { status: "success"; key: string; data: T }
  | { status: "error"; key: string; message: string };

export class LatestQuery<T> {
  private current: { abort: AbortController } | null = null;
  private state: QueryState<T> = { status: "idle" };
  constructor(private emit: (state: QueryState<T>) => void) {}
  private publish(state: QueryState<T>) { this.state = state; this.emit(state); }
  cancel(notify = true) {
    const run = this.current;
    this.current = null;
    run?.abort.abort();
    this.state = { status: "idle" };
    if (notify) this.emit(this.state);
  }
  async run(key: string, load: (signal: AbortSignal) => Promise<T>): Promise<void> {
    const previous = this.state.status === "success" && this.state.key === key ? this.state : null;
    this.current?.abort.abort();
    const run = { abort: new AbortController() };
    this.current = run;
    this.publish(previous ? { status: "loading", key, previous: previous.data } : { status: "loading", key });
    try {
      const data = await load(run.abort.signal);
      if (this.current === run && !run.abort.signal.aborted) this.publish({ status: "success", key, data });
    } catch (error) {
      if (this.current === run && !run.abort.signal.aborted) {
        this.publish({ status: "error", key, message: error instanceof Error ? error.message : "查询失败" });
      }
    } finally {
      if (this.current === run) this.current = null;
    }
  }
}
