import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getCourtroomEvents } from "@/lib/api/courtroom";
import type { CourtroomTrialEvent } from "@/lib/api/types";

function buildWebSocketUrl(path: string): string {
  if (typeof window === "undefined") {
    return "";
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}${path}`;
}

export function useCourtroomEvents(analysisId: string) {
  const initialHistory = useQuery({
    queryKey: ["courtroom-events", analysisId],
    queryFn: () => getCourtroomEvents(analysisId),
    enabled: Boolean(analysisId),
  });

  const [liveEvents, setLiveEvents] = useState<CourtroomTrialEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!analysisId || typeof window === "undefined") {
      return;
    }

    const url = buildWebSocketUrl(`/api/v1/courtroom/analysis/${analysisId}/events`);
    if (!url) {
      return;
    }

    const socket = new WebSocket(url);
    socket.onopen = () => {
      setConnected(true);
      setError(null);
    };
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as CourtroomTrialEvent;
        setLiveEvents((current) => {
          if (current.some((item) => item.event_id === payload.event_id)) {
            return current;
          }
          return [...current, payload];
        });
      } catch {
        setError("Received malformed courtroom event payload.");
      }
    };
    socket.onerror = () => {
      setError("Courtroom event stream failed.");
    };
    socket.onclose = () => {
      setConnected(false);
    };

    return () => {
      socket.close();
    };
  }, [analysisId]);

  const replayEvents = useMemo(() => {
    const combined = [...(initialHistory.data ?? []), ...liveEvents];
    const seen = new Set<string>();
    return combined.filter((event) => {
      if (seen.has(event.event_id)) {
        return false;
      }
      seen.add(event.event_id);
      return true;
    });
  }, [initialHistory.data, liveEvents]);

  return {
    events: replayEvents,
    isConnected: connected,
    error,
    isLoading: initialHistory.isLoading,
  };
}
