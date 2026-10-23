"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Container } from "@/components/layout/container";
import { staggerContainer, staggerItem } from "@/lib/utils/motion";
import { Scale, Search, MessageSquare, BarChart3 } from "lucide-react";
import { ParallaxSection } from "@/components/visuals/parallax-section";

export default function Home() {
  return (
    <div className="pb-20">
      <Container className="pt-16">
        <div className="legal-panel overflow-hidden p-8 md:p-12">
          <motion.div
            variants={staggerContainer}
            initial="initial"
            animate="animate"
            className="grid gap-10 md:grid-cols-[1.05fr_0.95fr]"
          >
            <motion.div variants={staggerItem} className="space-y-6">
              <p className="legal-chip inline-flex">
                NyayaAI Legal Stack
              </p>
              <h1 className="text-4xl font-semibold leading-[1.05] text-[var(--primary-900)] md:text-6xl">
                Litigation intelligence, built for actual court workflows.
              </h1>
              <p className="max-w-2xl text-base leading-7 text-[var(--neutral-600)]">
                Move from raw facts to strategic case understanding through a connected workspace: precedent
                retrieval, citation-grounded assistant answers, simulated courtroom deliberation, and outcome tendency analysis.
              </p>
              <div className="flex flex-wrap gap-4">
                <Link
                  href="/search"
                  className="legal-button-primary px-6 py-3 text-sm font-semibold"
                >
                  Start Similar Case Search
                </Link>
                <Link
                  href="/assistant"
                  className="legal-button-secondary px-6 py-3 text-sm font-semibold"
                >
                  Open Legal Assistant
                </Link>
              </div>
            </motion.div>
            <motion.div variants={staggerItem} className="space-y-4">
              <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
                <p className="text-xs uppercase tracking-[0.1em] text-[var(--neutral-500)]">Matter cockpit</p>
                <div className="mt-4 space-y-4 text-sm text-[var(--neutral-700)]">
                  {[
                    ["Search", "Multidimensional precedent retrieval", Search],
                    ["Assistant", "Citation-grounded legal responses", MessageSquare],
                    ["Courtroom", "Role-based legal argument stress-test", Scale],
                    ["Tendency", "Historical tendency and bias-aware confidence", BarChart3],
                  ].map(([name, description, Icon]) => (
                    <div key={String(name)} className="flex items-center gap-3">
                      <span className="rounded-lg border border-[var(--border)] bg-[var(--surface-alt)] p-2">
                        <Icon className="h-4 w-4 text-[var(--primary-700)]" />
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-[var(--primary-900)]">{String(name)}</p>
                        <p className="text-xs text-[var(--neutral-600)]">{String(description)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </Container>

      <ParallaxSection offset={14}>
        <Container className="mt-12">
          <div className="grid gap-4 md:grid-cols-4">
            {[
              ["9,537", "Labeled matters"],
              ["43", "Courts represented"],
              ["13", "Years of judgments"],
              ["4", "Integrated analysis modes"],
            ].map(([value, label]) => (
              <div key={String(label)} className="legal-panel p-5">
                <p className="text-3xl font-semibold text-[var(--primary-900)]">{value}</p>
                <p className="mt-1 text-xs uppercase tracking-[0.08em] text-[var(--neutral-500)]">{label}</p>
              </div>
            ))}
          </div>
        </Container>
      </ParallaxSection>

      <ParallaxSection offset={22}>
        <Container className="mt-16">
          <motion.div
            variants={staggerContainer}
            initial="initial"
            whileInView="animate"
            viewport={{ once: true }}
            className="grid gap-6 md:grid-cols-3"
          >
            {[
              {
                title: "1. Submit matter details",
                copy: "Upload a file or paste raw facts. The system normalizes source text for downstream analysis.",
              },
              {
                title: "2. Run layered legal analysis",
                copy: "Search, assistant, courtroom, and tendency engines generate complementary legal signals.",
              },
              {
                title: "3. Audit confidence and caveats",
                copy: "Review citations, confidence bands, drift flags, and limitations before drafting strategy.",
              },
            ].map((item) => (
              <motion.div key={item.title} variants={staggerItem}>
                <div className="legal-panel h-full p-6">
                  <h3 className="text-lg font-semibold text-[var(--primary-900)]">{item.title}</h3>
                  <p className="mt-3 text-sm text-[var(--neutral-600)]">{item.copy}</p>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </Container>
      </ParallaxSection>
    </div>
  );
}
