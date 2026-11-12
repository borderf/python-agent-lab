export type Citation = {
  sourceId: string;
  version: string;
  quote: string;
};

export type StreamEvent =
  | { type: "token"; text: string }
  | { type: "citation"; citation: Citation }
  | { type: "done"; answerId: string; needsReview: boolean }
  | { type: "error"; message: string; retryable: boolean };

export type AnswerState =
  | { status: "idle" }
  | { status: "connecting"; text: ""; citations: Citation[] }
  | { status: "streaming"; text: string; citations: Citation[] }
  | { status: "done"; text: string; citations: Citation[]; answerId: string; needsReview: boolean }
  | { status: "stopped"; text: string; citations: Citation[] }
  | { status: "error"; text: string; citations: Citation[]; message: string; retryable: boolean };

export type AnswerAction =
  | { type: "start" }
  | { type: "tokens"; text: string }
  | { type: "event"; event: StreamEvent }
  | { type: "stop" }
  | { type: "error"; message: string; retryable: boolean };

function terminal(state: AnswerState): boolean {
  return state.status === "done" || state.status === "stopped" || state.status === "error";
}

function currentText(state: AnswerState): string {
  return state.status === "idle" ? "" : state.text;
}

function currentCitations(state: AnswerState): Citation[] {
  return state.status === "idle" ? [] : state.citations;
}

export function reduceAnswer(state: AnswerState, action: AnswerAction): AnswerState {
  switch (action.type) {
    case "start":
      return { status: "connecting", text: "", citations: [] };
    case "tokens":
      if (state.status !== "connecting" && state.status !== "streaming") return state;
      return { status: "streaming", text: state.text + action.text, citations: state.citations };
    case "event": {
      if (terminal(state)) return state;
      const event = action.event;
      if (event.type === "token") {
        if (state.status !== "connecting" && state.status !== "streaming") return state;
        return { status: "streaming", text: state.text + event.text, citations: state.citations };
      }
      if (event.type === "citation") {
        if (state.status !== "connecting" && state.status !== "streaming") return state;
        const exists = state.citations.some(
          (item) => item.sourceId === event.citation.sourceId
            && item.version === event.citation.version && item.quote === event.citation.quote,
        );
        return exists ? state : {
          status: "streaming",
          text: state.text,
          citations: [...state.citations, event.citation],
        };
      }
      if (state.status !== "connecting" && state.status !== "streaming") return state;
      if (event.type === "done") {
        return {
          status: "done",
          text: currentText(state),
          citations: currentCitations(state),
          answerId: event.answerId,
          needsReview: event.needsReview,
        };
      }
      return {
        status: "error",
        text: currentText(state),
        citations: currentCitations(state),
        message: event.message,
        retryable: event.retryable,
      };
    }
    case "stop":
      if (state.status !== "connecting" && state.status !== "streaming") return state;
      return { status: "stopped", text: state.text, citations: state.citations };
    case "error":
      if (terminal(state)) return state;
      return {
        status: "error",
        text: currentText(state),
        citations: currentCitations(state),
        message: action.message,
        retryable: action.retryable,
      };
  }
}
