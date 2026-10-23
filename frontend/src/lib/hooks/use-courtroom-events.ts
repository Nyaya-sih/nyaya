import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getCourtroomEvents } from "@/lib/api/courtroom";
import type { CourtroomTrialEvent } from "@/lib/api/types";

export function useCourtroomEvents(analysisId: string, running = true) {
  // HTTP polling also recovers missed events when a proxy cannot forward sockets.
  const history = useQuery({
    queryKey: ["courtroom-events", analysisId],
    queryFn: () => getCourtroomEvents(analysisId),
    enabled: Boolean(analysisId),
    refetchInterval: running ? 1500 : false,
  });
  const [live, setLive] = useState<CourtroomTrialEvent[]>([]);
  const [connection, setConnection] = useState({ id: "", connected: false });

  useEffect(() => {
    if (!analysisId || !running) return;
    const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const url = new URL(`${base}/api/v1/courtroom/analysis/${analysisId}/events`, window.location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(url);
    let disposed = false;
    socket.onopen = () => {
      if (!disposed) setConnection({ id: analysisId, connected: true });
    };
    socket.onmessage = (message) => {
      if (disposed) return;
      try {
        const event = JSON.parse(message.data) as CourtroomTrialEvent;
        if (event.session_id !== analysisId || !event.event_id) return;
        setLive((items) => items.some((item) => item.event_id === event.event_id) ? items : [...items.filter((item) => item.session_id === analysisId), event]);
      } catch {
        // The polled canonical log remains the source of truth.
      }
    };
    socket.onclose = () => {
      if (!disposed) setConnection({ id: analysisId, connected: false });
    };
    return () => {
      disposed = true;
      socket.close();
    };
  }, [analysisId, running]);

  const combined = new Map<string, CourtroomTrialEvent>();
  for (const event of [...(history.data ?? []), ...live]) {
    if (event.session_id === analysisId) combined.set(event.event_id, event);
  }
  return {
    events: [...combined.values()].sort((a, b) => a.timestamp.localeCompare(b.timestamp)),
    isConnected: running && connection.id === analysisId && connection.connected,
    error: history.error ? "Unable to refresh the hearing transcript. Retrying automatically." : null,
    isLoading: history.isLoading,
  };
}
