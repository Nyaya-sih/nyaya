import Link from "next/link";
import { Container } from "@/components/layout/container";

interface PageHeaderProps {
  title: string;
  breadcrumb?: Array<{ label: string; href?: string }>;
  description?: string;
}

export function PageHeader({ title, breadcrumb, description }: PageHeaderProps) {
  return (
    <Container className="py-10">
      {breadcrumb && (
        <div className="mb-3 flex flex-wrap gap-2 text-xs text-[var(--neutral-500)]">
          {breadcrumb.map((item, index) => (
            <span key={`${item.label}-${index}`}>
              {item.href ? (
                <Link href={item.href} className="hover:text-[var(--primary-700)]">
                  {item.label}
                </Link>
              ) : (
                item.label
              )}
              {index < breadcrumb.length - 1 && <span className="mx-2">/</span>}
            </span>
          ))}
        </div>
      )}
      <h1 className="text-3xl font-semibold text-[var(--primary-900)] md:text-4xl">
        {title}
      </h1>
      {description && (
        <p className="mt-2 max-w-2xl text-sm text-[var(--neutral-600)]">
          {description}
        </p>
      )}
    </Container>
  );
}
