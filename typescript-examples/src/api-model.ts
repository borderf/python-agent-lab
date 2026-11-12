import type { Answer, Citation } from "./contracts.js";

export type Page<T> = {
  items: T[];
  nextCursor: string | null;
};

export type CitationPage = Page<Citation>;
export type AnswerPage = Page<Answer>;

export function firstOrNull<T>(items: readonly T[]): T | null {
  const first = items[0];
  return first === undefined ? null : first;
}

export function pick<T, K extends keyof T>(value: T, keys: readonly K[]): Pick<T, K> {
  const result = {} as Pick<T, K>;
  for (const key of keys) result[key] = value[key];
  return result;
}

export function mergePages<T>(pages: readonly Page<T>[]): T[] {
  return pages.flatMap((page) => page.items);
}