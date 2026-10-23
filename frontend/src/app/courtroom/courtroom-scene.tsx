"use client";

import { useEffect, useRef, useState } from "react";
import { BookOpen, Check, Circle, Gavel, HeartHandshake, Landmark, LoaderCircle, Pause, Play, Scale, Shield, type LucideIcon } from "lucide-react";
import type { CourtroomAnalysisResponse, CourtroomTrialEvent } from "@/lib/api/types";

export const COURTROOM_ROLES: Array<{ name: string; label: string; shortLabel: string; mandate: string; icon: LucideIcon; seat: string }> = [
  { name: "Presiding Judge", label: "Presiding Judge", shortLabel: "Presiding Judge", mandate: "Reviews the conclusion against the record", icon: Gavel, seat: "judge" },
  { name: "Prosecution Counsel", label: "Prosecutor", shortLabel: "Prosecutor", mandate: "Tests the case for the prosecution", icon: Scale, seat: "prosecution" },
  { name: "Defense Counsel", label: "Defense Lawyer", shortLabel: "Defense", mandate: "Challenges the evidence and protects rights", icon: Shield, seat: "defense" },
  { name: "Constitutional Expert", label: "Constitutional Expert", shortLabel: "Constitutional", mandate: "Examines fundamental rights, proportionality, and due process", icon: Landmark, seat: "constitutional" },
  { name: "Legal Analyst", label: "Legal Advisor", shortLabel: "Legal Advisor", mandate: "Examines statutes, procedure, and legal gaps", icon: BookOpen, seat: "advisor" },
  { name: "Moral Advisor", label: "Moral Advisor", shortLabel: "Moral Advisor", mandate: "Examines harm and fairness, without treating moral views as law", icon: HeartHandshake, seat: "moral" },
];

export function CourtroomScene({ events, running, terminal, missing, selectedRole, inspectorOpen, report, onSelect }: {
  events: CourtroomTrialEvent[];
  running: boolean;
  terminal: boolean;
  missing: boolean;
  selectedRole: string;
  inspectorOpen: boolean;
  report?: CourtroomAnalysisResponse;
  onSelect: (role: string) => void;
}) {
  const root = useRef<HTMLElement>(null);
  const [motionPaused, setMotionPaused] = useState(false);

  useEffect(() => {
    if (motionPaused) return;
    let disposed = false;
    let cleanup: (() => void) | undefined;
    void Promise.all([import("gsap"), import("gsap/ScrollTrigger")]).then(([{ gsap }, { ScrollTrigger }]) => {
      if (disposed) return;
      gsap.registerPlugin(ScrollTrigger);
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.fromTo(".scene-agent", { y: 14, opacity: 0 }, {
        y: 0, opacity: 1, duration: 0.55, stagger: 0.065, ease: "power2.out",
        scrollTrigger: { trigger: root.current, start: "top 92%", once: true },
        clearProps: "transform,opacity",
      });
      }, root);
      cleanup = () => media.revert();
    }).catch(() => { /* The chamber remains usable if optional motion cannot load. */ });
    return () => { disposed = true; cleanup?.(); };
  }, [motionPaused]);

  return <section ref={root} className="courtroom-chamber" data-motion-paused={motionPaused} aria-label="Visual courtroom">
    <header className="chamber-topline"><span><i className={running ? "session-dot session-dot-live" : "session-dot"} />{running ? "Hearing in progress" : terminal ? "Hearing closed" : "The deliberation chamber"}</span><button type="button" className="motion-toggle" aria-pressed={motionPaused} onClick={() => setMotionPaused(!motionPaused)} aria-label={motionPaused ? "Resume motion" : "Pause motion"}>{motionPaused ? <Play size={13} /> : <Pause size={13} />}<span>{motionPaused ? "Motion off" : "Motion on"}</span></button></header>
    <div className="courtroom-scene">
      <div className="room-architecture" aria-hidden="true">
        <div className="room-back-wall"><span /><span /><span /></div>
        <div className="room-seal"><Scale size={24} strokeWidth={1.2} /></div>
        <div className="room-window window-left" /><div className="room-window window-right" />
        <div className="room-floor" /><div className="room-aisle" />
        <div className="judge-platform" /><div className="judge-bench"><span>NYAYA AI</span><i /><i /></div>
        <div className="counsel-desk desk-prosecution" /><div className="counsel-desk desk-defense" />
        <div className="advisory-table" /><div className="gallery-rail" />
      </div>
      <div className="courtroom-seats">
        {COURTROOM_ROLES.map((role) => {
          const roleEvents = events.filter((event) => event.role === role.name);
          const latest = roleEvents.at(-1);
          const substantive = roleEvents.filter((event) => event.event_type !== "frame").at(-1);
          const active = running && latest?.event_type === "frame";
          const fallback = latest?.model_provider === "fallback" || report?.role_analyses.some((item) => item.role_name === role.name && item.degraded);
          let state = report || running ? "Waiting for turn" : "Awaiting case";
          if (active) state = latest?.stage === "rebuttal" ? "Preparing rebuttal" : role.seat === "judge" ? "Reviewing draft" : "Reviewing case";
          else if (substantive) state = substantive.event_type === "position" ? "Opinion ready" : substantive.event_type === "rebuttal" || substantive.event_type === "revision" ? "Rebuttal ready" : "Review ready";
          if (role.seat === "judge" && report?.judge_review) state = report.judge_review.approved && !report.judge_review.degraded ? "Summary approved" : report.judge_review.degraded ? "Review unavailable" : "Changes required";
          else if (fallback && !active) state = "Fallback / review needed";
          if (report?.status === "cancelled") state = "Hearing cancelled";
          if (report?.status === "failed") state = "Hearing interrupted";
          if (missing) state = "Session unavailable";
          const Icon = role.icon;
          return <div className={`scene-agent scene-${role.seat}`} key={role.name}>
            <button type="button" className={`agent-seat seat-${role.seat}`} data-selected={inspectorOpen && selectedRole === role.name} data-active={active} aria-label={`${role.label}: ${state}. Inspect public reasons and evidence`} aria-pressed={inspectorOpen && selectedRole === role.name} aria-controls="agent-report" onClick={() => onSelect(role.name)}>
              <span className="agent-figure" aria-hidden="true"><span className="agent-blob"><span className="blob-highlight" /><span className="blob-face"><i /><i /><b /></span><span className="blob-role"><Icon size={16} strokeWidth={1.7} /></span>{role.seat === "judge" && <span className="judge-collar" />}</span><span className="blob-shadow" /></span>
              <span className="agent-name">{role.shortLabel}</span>
              <span className="agent-state">{active ? <LoaderCircle size={10} className="hearing-spinner" /> : substantive && !fallback ? <Check size={10} /> : <Circle size={7} />}{state}</span>
              <span className="agent-inspect-hint">{inspectorOpen && selectedRole === role.name ? "Viewing insight" : "View insight"}</span>
            </button>
          </div>;
        })}
      </div>
    </div>
    <footer className="chamber-caption"><span className="scene-key"><i />Independent roles, shared record</span><span>Select an agent to follow its public reasoning.</span></footer>
  </section>;
}
