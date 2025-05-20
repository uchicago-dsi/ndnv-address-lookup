import { expose } from "comlink";
import type { SearchWorkerClass } from "./types";
const SearchWorker: SearchWorkerClass = {
  search: async (query: string) => {
    return [
      query,
      'foo',
      'bar'
    ];
  }
}

expose(SearchWorker);