"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Scale, Search, MessageSquare, BarChart3, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { Container } from "@/components/layout/container";
import { useUiStore } from "@/lib/stores/ui-store";

const navItems = [
  { label: "Similar Cases", href: "/search", icon: Search },
  { label: "Courtroom", href: "/courtroom", icon: Scale },
  { label: "Assistant", href: "/assistant", icon: MessageSquare },
  { label: "Tendency", href: "/tendency", icon: BarChart3 },
];

export function Navbar() {
  const pathname = usePathname();
  const theme = useUiStore((state) => state.theme);
  const toggleTheme = useUiStore((state) => state.toggleTheme);

  return (
    <div className="sticky top-0 z-50 border-b border-[var(--border)] bg-[color:var(--background)]/88 backdrop-blur-xl">
      <Container className="flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-3 text-lg font-semibold">
          <span className="rounded-md border border-[var(--primary-500)]/40 bg-[var(--primary-800)] px-2 py-1 text-[11px] font-bold tracking-[0.12em] text-white">
            NyayaAI
          </span>
          <span className="hidden text-sm text-[var(--neutral-600)] sm:inline">
            Litigation Intelligence Workspace
          </span>
        </Link>

        <nav className="hidden items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)]/80 p-1 text-sm md:flex">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href) && !item.disabled;
            return (
              <Link
                key={item.href}
                href={item.disabled ? "#" : item.href}
                className={cn(
                  "flex items-center gap-2 rounded-full px-3 py-1.5 transition-all",
                  item.disabled
                    ? "text-[var(--neutral-400)]"
                    : isActive
                      ? "bg-[var(--primary-700)] text-white"
                      : "text-[var(--neutral-700)] hover:bg-[var(--surface-alt)] hover:text-[var(--primary-700)]"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
                {item.disabled && (
                  <span className="ml-1 rounded-full border border-[var(--border)] px-2 py-0.5 text-[10px] text-[var(--neutral-400)]">
                    Soon
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <button
          type="button"
          onClick={toggleTheme}
          className="flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs text-[var(--neutral-600)] transition hover:border-[var(--accent-300)] hover:text-[var(--primary-700)]"
          aria-label="Toggle theme"
        >
          {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
          {theme === "light" ? "Dark" : "Light"}
        </button>
      </Container>
    </div>
  );
}
