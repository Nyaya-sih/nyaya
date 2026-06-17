"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Download, SlidersHorizontal } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import type { SearchResponse } from "@/lib/api/types";
import { exportAsCsv, exportAsJson } from "@/lib/utils/export-results";

export function ResultsHeader({ response }: { response: SearchResponse }) {
  const reduceMotion = useReducedMotion();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  return (
    <motion.div
      className="legal-panel flex flex-col gap-4 p-6 md:flex-row md:items-center md:justify-between"
      initial={reduceMotion ? false : { opacity: 0, y: 8 }}
      animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: "easeOut" }}
    >
      <div>
        <p className="legal-chip inline-flex">{response.total_results} matches</p>
        <p className="mt-3 text-lg font-semibold text-[var(--primary-900)]">{response.query_summary}</p>
        <p className="mt-1 text-xs uppercase tracking-[0.08em] text-[var(--neutral-500)]">
          Processing {Math.round(response.search_time_ms)}ms
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href="/search"
          className="legal-button-secondary inline-flex items-center gap-2 px-4 py-2 text-xs"
        >
          <SlidersHorizontal className="h-4 w-4" />
          Modify Search
        </Link>
        <div ref={menuRef} className="relative">
          <button
            type="button"
            onClick={() => setOpen((prev) => !prev)}
            aria-haspopup="true"
            aria-expanded={open}
            className="legal-button-primary inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold"
          >
            <Download className="h-4 w-4" />
            Export
          </button>
          {open && (
            <div className="absolute right-0 z-10 mt-2 w-40 rounded-xl border border-[var(--border)] bg-[var(--surface)] py-1 shadow-lg">
              <button
                type="button"
                onClick={() => { exportAsCsv(response); setOpen(false); }}
                className="block w-full px-4 py-2 text-left text-xs text-[var(--neutral-600)] hover:bg-[var(--surface-alt)]"
              >
                Export as CSV
              </button>
              <button
                type="button"
                onClick={() => { exportAsJson(response); setOpen(false); }}
                className="block w-full px-4 py-2 text-left text-xs text-[var(--neutral-600)] hover:bg-[var(--surface-alt)]"
              >
                Export as JSON
              </button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
