export interface SearchWorkerClass {
  search(query: string): Promise<string[]>;
}