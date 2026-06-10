import { Message } from './types';

export interface StreamState {
  loading: boolean;
  content: string;
  optimisticMsg: Message | null;
}

type Listener = (state: StreamState) => void;

class StreamStore {
  private states = new Map<string, StreamState>();
  private listeners = new Map<string, Set<Listener>>();

  getState(convId: string): StreamState {
    return this.states.get(convId) || { loading: false, content: '', optimisticMsg: null };
  }

  updateState(convId: string, updater: (prev: StreamState) => StreamState) {
    const prev = this.getState(convId);
    const next = updater(prev);
    this.states.set(convId, next);
    
    const convListeners = this.listeners.get(convId);
    if (convListeners) {
      convListeners.forEach(fn => fn(next));
    }
  }

  subscribe(convId: string, fn: Listener) {
    if (!this.listeners.has(convId)) {
      this.listeners.set(convId, new Set());
    }
    this.listeners.get(convId)!.add(fn);
    return () => {
      this.listeners.get(convId)?.delete(fn);
    };
  }
}

export const streamStore = new StreamStore();
