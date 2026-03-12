"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Container } from "@/components/layout/container";
import { GradientText } from "@/components/shared/gradient-text";
import { AnimatedCounter } from "@/components/shared/animated-counter";
import { SpotlightCard } from "@/components/shared/spotlight-card";
import { ShimmerCard } from "@/components/shared/shimmer-card";
import { staggerContainer, staggerItem } from "@/lib/utils/motion";

export default function Home() {
  return (
    <div className="pb-20">
      <Container className="pt-20">
        <ShimmerCard className="bg-legal-gradient">
          <motion.div
            variants={staggerContainer}
            initial="initial"
            animate="animate"
            className="grid gap-8 md:grid-cols-[1.1fr_0.9fr]"
          >
            <motion.div variants={staggerItem} className="space-y-6">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--neutral-500)]">
                NyayaAI • Similar Case Retrieval
              </p>
              <h1 className="text-4xl font-semibold leading-tight text-[var(--primary-900)] md:text-5xl">
                <GradientText>Find precedents that matter</GradientText>
              </h1>
              <p className="text-sm text-[var(--neutral-600)] md:text-base">
                AI-powered case law research for Indian High Court judgments. Surface the most relevant
                precedents with multi-dimensional similarity scoring and transparent reasoning.
              </p>
              <div className="flex flex-wrap gap-4">
                <Link
                  href="/search"
                  className="rounded-full bg-[var(--primary-700)] px-6 py-3 text-sm font-semibold text-white"
                >
                  Upload Case Document
                </Link>
                <Link
                  href="/search"
                  className="rounded-full border border-[var(--border)] px-6 py-3 text-sm text-[var(--neutral-700)]"
                >
                  Search by Text
                </Link>
              </div>
            </motion.div>
            <motion.div variants={staggerItem} className="space-y-4">
              <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
                <p className="text-xs uppercase text-[var(--neutral-500)]">Live intelligence</p>
                <p className="mt-2 text-2xl font-semibold text-[var(--primary-900)]">
                  Cross-encoder precision ranking
                </p>
                <p className="mt-3 text-sm text-[var(--neutral-600)]">
                  Compare factual, legal, and outcome similarity with weighted scoring and explanations.
                </p>
              </div>
              <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
                <p className="text-xs uppercase text-[var(--neutral-500)]">Trust & transparency</p>
                <p className="mt-2 text-2xl font-semibold text-[var(--primary-900)]">
                  Built for legal professionals
                </p>
                <p className="mt-3 text-sm text-[var(--neutral-600)]">
                  Clear disclaimers, auditable sources, and confidence indicators in every report.
                </p>
              </div>
            </motion.div>
          </motion.div>
        </ShimmerCard>
      </Container>

      <Container className="mt-14">
        <div className="grid gap-4 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 text-center md:grid-cols-4 md:text-left">
          <div>
            <p className="text-xs text-[var(--neutral-500)]">Indexed cases</p>
            <p className="text-2xl font-semibold text-[var(--primary-900)]">
              <AnimatedCounter value={9718} suffix="+" />
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--neutral-500)]">Courts covered</p>
            <p className="text-2xl font-semibold text-[var(--primary-900)]">
              <AnimatedCounter value={43} />
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--neutral-500)]">Years of data</p>
            <p className="text-2xl font-semibold text-[var(--primary-900)]">
              <AnimatedCounter value={13} />
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--neutral-500)]">Similarity layers</p>
            <p className="text-2xl font-semibold text-[var(--primary-900)]">
              <AnimatedCounter value={5} />
            </p>
          </div>
        </div>
      </Container>

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
              title: "1. Upload your case",
              copy: "Drag a PDF or paste text. We extract structured metadata automatically.",
            },
            {
              title: "2. AI analyzes & matches",
              copy: "Embeddings and cross-encoder reranking surface the most relevant precedents.",
            },
            {
              title: "3. Review with confidence",
              copy: "Compare scores, statutes, and reasoning before building your argument.",
            },
          ].map((item) => (
            <motion.div key={item.title} variants={staggerItem}>
              <SpotlightCard>
                <h3 className="text-lg font-semibold text-[var(--primary-900)]">{item.title}</h3>
                <p className="mt-3 text-sm text-[var(--neutral-600)]">{item.copy}</p>
              </SpotlightCard>
            </motion.div>
          ))}
        </motion.div>
      </Container>

      <Container className="mt-16">
        <div className="grid gap-6 md:grid-cols-2">
          {[
            {
              title: "Multi-level similarity",
              copy: "Factual, legal, outcome, court, and temporal scores in every result.",
            },
            {
              title: "Smart filters",
              copy: "Filter by court, case type, date range, and verdict instantly.",
            },
            {
              title: "Cross-encoder reranking",
              copy: "Precision-first ranking to avoid missing the most relevant precedents.",
            },
            {
              title: "AI-powered explanations",
              copy: "Understand why a case was suggested and how it aligns to your facts.",
            },
          ].map((item) => (
            <SpotlightCard key={item.title}>
              <h3 className="text-lg font-semibold text-[var(--primary-900)]">{item.title}</h3>
              <p className="mt-3 text-sm text-[var(--neutral-600)]">{item.copy}</p>
            </SpotlightCard>
          ))}
        </div>
      </Container>
    </div>
  );
}
