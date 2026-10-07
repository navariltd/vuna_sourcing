import { onBeforeUnmount } from "vue";
import { io } from "socket.io-client";
import type { Socket } from "socket.io-client";

declare global {
  interface Window {
    site_name?: string;
    socketio_port?: number | null;
    dev_server?: number | boolean;
  }
}

let socket: Socket | null = null;

function socketUrl() {
  const { protocol, hostname, origin } = window.location;
  const host =
    window.dev_server && window.socketio_port
      ? `${protocol}//${hostname}:${window.socketio_port}`
      : origin;
  return `${host}/${window.site_name || hostname}`;
}

function connection(): Socket {
  socket ??= io(socketUrl(), { withCredentials: true });
  return socket;
}

export function useRealtime<T>(
  event: string,
  handler: (data: T) => void,
  onReconnect?: () => void,
) {
  const realtime = connection();
  const reconnected = () => onReconnect?.();

  realtime.on(event, handler);
  realtime.io.on("reconnect", reconnected);

  onBeforeUnmount(() => {
    realtime.off(event, handler);
    realtime.io.off("reconnect", reconnected);
  });
}
