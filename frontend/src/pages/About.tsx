export function About() {
  return (
    <div className="max-w-2xl space-y-6 text-sm leading-relaxed text-neutral-700 dark:text-neutral-300">
      <h1 className="text-xl font-semibold text-neutral-900 dark:text-neutral-50">About this app</h1>

      <section className="space-y-2">
        <h2 className="text-base font-medium text-neutral-900 dark:text-neutral-50">
          A Poisson-process order simulator
        </h2>
        <p>
          Orders arrive over <code>/ws/orders</code> from a non-homogeneous Poisson process (a
          thinning algorithm), not a scripted loop. Its arrival-rate model deliberately reuses the
          same weekday/daypart demand shape from <code>config/business_rules.yaml</code> that the
          batch data generator uses for the Streamlit dashboard — one demand model, two consumption
          modes: batch (a day rolled up into marts) and live (individual events as they happen).
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-base font-medium text-neutral-900 dark:text-neutral-50">
          No message broker
        </h2>
        <p>
          At this event volume, Kafka or Redis would add real infrastructure — a broker to install,
          run, and document — for no benefit a WebSocket doesn&rsquo;t already provide. FastAPI holds
          a rolling 15-minute aggregate and a capped session history in memory and pushes new events
          straight to connected clients.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-base font-medium text-neutral-900 dark:text-neutral-50">
          Why a second app, not one bigger one
        </h2>
        <p>
          Streamlit isn&rsquo;t built for real-time push updates, so the live stream is a separate
          FastAPI + WebSockets app rather than a retrofit. The batch dashboard (
          <code>app/</code>, eight pages) stays exactly as it was — finished, working,
          spec-complete — reading straight from the dbt-built marts. This app is a second,
          complementary showcase built on genuinely new data the batch pipeline doesn&rsquo;t have:
          live and session state, not a duplicate of the historical marts.
        </p>
      </section>

      <p className="text-neutral-400">
        See <code>docs/project_decisions.md</code> and <code>docs/architecture.md</code> in the
        repository for the fuller reasoning.
      </p>
    </div>
  )
}
