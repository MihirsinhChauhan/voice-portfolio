import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-background font-sans">
      <main className="mx-auto max-w-3xl px-6 py-24 sm:px-12">
        {/* Hero */}
        <section className="mb-20">
          <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
            Mihir Chauhan
          </h1>
          <p className="mt-4 text-xl text-muted-foreground">
            Backend & Systems Engineer
          </p>
          <p className="mt-6 text-lg leading-relaxed text-foreground/90">
            I build scalable systems, APIs, and infrastructure. Passionate about
            voice AI, distributed systems, and clean architecture.
          </p>
        </section>

        {/* Projects teaser */}
        <section className="mb-20">
          <h2 className="text-2xl font-semibold text-foreground">Projects</h2>
          <p className="mt-3 text-muted-foreground">
            From real-time voice agents to high-throughput backends — I&apos;ve
            worked across the stack. Curious about the details?
          </p>
        </section>

        {/* CTA */}
        <section className="rounded-2xl border border-border bg-card p-8 text-card-foreground shadow-sm">
          <h2 className="text-2xl font-semibold">
            Want to know about me? Talk to Melvin
          </h2>
          <p className="mt-3 text-muted-foreground">
            Have a conversation with Melvin — my AI voice assistant. Ask about
            my work, projects, or book a call.
          </p>
          <Link
            href="/talk"
            className="mt-6 inline-flex h-12 items-center justify-center rounded-full bg-primary px-8 font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Talk to Melvin
          </Link>
        </section>
      </main>
    </div>
  );
}
