import * as Comlink from "comlink";
import type { SearchWorkerClass } from "./types";

// Create a worker instance
const worker = new Worker(new URL("./SearchWorker.ts", import.meta.url), {
  type: "module",
});

// Wrap the worker with Comlink
const remoteWorker = Comlink.wrap<SearchWorkerClass>(worker);

export default remoteWorker;
