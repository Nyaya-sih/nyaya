"use client";

import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";

function FloatingPaths({ position }: { position: number }) {
  const paths = Array.from({ length: 36 }, (_, i) => ({
    id: i,
    d: `M-${380 - i * 5 * position} -${189 + i * 6}C-${
      380 - i * 5 * position
    } -${189 + i * 6} -${312 - i * 5 * position} ${216 - i * 6} ${
      152 - i * 5 * position
    } ${343 - i * 6}C${616 - i * 5 * position} ${470 - i * 6} ${
      684 - i * 5 * position
    } ${875 - i * 6} ${684 - i * 5 * position} ${875 - i * 6}`,
    width: 0.5 + i * 0.03,
  }));

  return (
    <div className="pointer-events-none absolute inset-0">
      <svg
        className="h-full w-full text-[var(--primary-900)] dark:text-white"
        viewBox="0 0 696 316"
        fill="none"
      >
        <title>Background Paths</title>
        {paths.map((path) => (
          <motion.path
            key={path.id}
            d={path.d}
            stroke="currentColor"
            strokeWidth={path.width}
            strokeOpacity={0.06 + path.id * 0.012}
            initial={{ pathLength: 0.3, opacity: 0.5 }}
            animate={{
              pathLength: 1,
              opacity: [0.2, 0.45, 0.2],
              pathOffset: [0, 1, 0],
            }}
            transition={{
              duration: 20 + (path.id % 10),
              repeat: Number.POSITIVE_INFINITY,
              ease: "linear",
            }}
          />
        ))}
      </svg>
    </div>
  );
}

export function BackgroundPaths({
  title = "Background Paths",
  compact = false,
}: {
  title?: string;
  compact?: boolean;
}) {
  const words = title.split(" ");

  return (
    <div
      className={`relative w-full overflow-hidden ${
        compact
          ? "min-h-[320px] rounded-2xl border border-[var(--border)] bg-[var(--surface)]"
          : "min-h-screen bg-white dark:bg-neutral-950"
      }`}
    >
      <div className="absolute inset-0">
        <FloatingPaths position={1} />
        <FloatingPaths position={-1} />
      </div>

      <div className="relative z-10 mx-auto flex h-full max-w-4xl flex-col items-center justify-center px-4 py-14 text-center md:px-6">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.2 }}
          className="mx-auto max-w-4xl"
        >
          <h1
            className={`mb-6 font-bold tracking-tighter text-[var(--primary-900)] ${
              compact ? "text-3xl sm:text-4xl md:text-5xl" : "text-5xl sm:text-7xl md:text-8xl"
            }`}
          >
            {words.map((word, wordIndex) => (
              <span key={wordIndex} className="mr-3 inline-block last:mr-0">
                {word.split("").map((letter, letterIndex) => (
                  <motion.span
                    key={`${wordIndex}-${letterIndex}`}
                    initial={{ y: 80, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{
                      delay: wordIndex * 0.1 + letterIndex * 0.03,
                      type: "spring",
                      stiffness: 150,
                      damping: 25,
                    }}
                    className="inline-block bg-gradient-to-r from-[var(--primary-900)] to-[var(--primary-700)] bg-clip-text text-transparent"
                  >
                    {letter}
                  </motion.span>
                ))}
              </span>
            ))}
          </h1>

          {!compact && (
            <div className="inline-block overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-px shadow-lg">
              <Button variant="ghost" className="rounded-[1.15rem] px-8 py-6 text-lg font-semibold">
                <span className="opacity-90 transition-opacity group-hover:opacity-100">Discover Excellence</span>
                <span className="ml-3 opacity-70 transition-all duration-300 group-hover:translate-x-1.5 group-hover:opacity-100">
                  →
                </span>
              </Button>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
