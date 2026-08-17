<script>
  import { routeStore } from '$lib/stores/routeStore.js';

  // Chart dimensions
  const CHART_HEIGHT = 90;
  const BAR_GAP = 3;

  let scores = [];
  let maxScore = 1;
  let barWidth = 20;
  let chartWidth = 20;

  $: {
    scores = $routeStore.hazard_scores;
    maxScore = scores.length > 0 ? Math.max(...scores.map(s => s.total_score), 0.01) : 1;
    barWidth = scores.length > 0
      ? Math.max(8, Math.floor((260 - BAR_GAP * scores.length) / scores.length))
      : 20;
    chartWidth = scores.length * (barWidth + BAR_GAP) + 10;
  }

  function formatTime(isoStr) {
    return new Date(isoStr).toLocaleTimeString('en-IN', {
      hour: '2-digit', minute: '2-digit', hour12: true
    });
  }

  function barColor(score, isOptimal, maxScore) {
    if (isOptimal) return '#f97316';
    const ratio = score.total_score / maxScore;
    if (ratio < 0.35) return '#22c55e';
    if (ratio < 0.65) return '#eab308';
    return '#ef4444';
  }

  function barHeight(score, maxScore) {
    return Math.max(4, (score.total_score / maxScore) * CHART_HEIGHT);
  }

  function handleBarClick(score) {
    routeStore.update(s => ({ ...s, selected_departure: score.departure_time }));
  }
</script>

{#if scores.length > 0}
  <div class="picker-card card fade-in">
    <div class="picker-header">
      <div class="picker-title font-data">Departure Window</div>
      <div class="picker-subtitle">Hazard score S(t) — lower is safer</div>
    </div>

    <!-- Legend -->
    <div class="legend">
      <span class="legend-dot" style="background:#22c55e"></span><span>Safe</span>
      <span class="legend-dot" style="background:#eab308"></span><span>Moderate</span>
      <span class="legend-dot" style="background:#ef4444"></span><span>High risk</span>
      <span class="legend-dot" style="background:#f97316"></span><span>Optimal</span>
    </div>

    <!-- SVG Bar Chart -->
    <div class="chart-scroll">
      <svg
        width={chartWidth}
        height={CHART_HEIGHT + 30}
        viewBox={"0 0 " + chartWidth + " " + (CHART_HEIGHT + 30)}
        role="img"
        aria-label="Hazard score chart across departure windows"
      >
        {#each scores as score, i}
          <rect
            x={i * (barWidth + BAR_GAP) + 5}
            y={CHART_HEIGHT - barHeight(score, maxScore)}
            width={barWidth}
            height={barHeight(score, maxScore)}
            rx="3"
            fill={barColor(score, score.is_optimal, maxScore)}
            opacity={score.is_optimal ? 1 : 0.65}
            style="cursor:pointer; transition: opacity 150ms ease;"
            role="button"
            tabindex="0"
            aria-label={"Depart at " + formatTime(score.departure_time) + ", score " + score.total_score.toFixed(2)}
            on:click={() => handleBarClick(score)}
            on:keydown={(e) => e.key === 'Enter' && handleBarClick(score)}
          />

          {#if score.is_optimal}
            <rect
              x={i * (barWidth + BAR_GAP) + 3}
              y={CHART_HEIGHT - barHeight(score, maxScore) - 2}
              width={barWidth + 4}
              height={barHeight(score, maxScore) + 4}
              rx="4"
              fill="none"
              stroke="#f97316"
              stroke-width="1.5"
              opacity="0.6"
            />
          {/if}

          {#if scores.length <= 12 || i % 2 === 0}
            <text
              x={i * (barWidth + BAR_GAP) + 5 + barWidth / 2}
              y={CHART_HEIGHT + 18}
              text-anchor="middle"
              font-size="8"
              fill={score.is_optimal ? '#f97316' : '#475569'}
              font-family="Inter, sans-serif"
              font-weight={score.is_optimal ? '700' : '400'}
            >
              {formatTime(score.departure_time).replace(' AM','a').replace(' PM','p')}
            </text>
          {/if}
        {/each}
      </svg>
    </div>

    <!-- Optimal callout -->
    {#if $routeStore.optimal_departure}
      <div class="optimal-callout">
        <span class="optimal-icon">⭐</span>
        <div>
          <div class="optimal-time font-data">
            {formatTime($routeStore.optimal_departure)}
          </div>
          <div class="optimal-label">Optimal departure</div>
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .picker-card {
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .picker-header {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .picker-title {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .picker-subtitle {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .legend {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    font-size: 10px;
    color: var(--text-muted);
  }

  .legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }

  .chart-scroll {
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .optimal-callout {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    background: rgba(249, 115, 22, 0.08);
    border: 1px solid rgba(249, 115, 22, 0.2);
    border-radius: var(--radius-sm);
    padding: var(--space-2) var(--space-3);
  }

  .optimal-icon { font-size: 18px; }

  .optimal-time {
    font-size: 16px;
    font-weight: 700;
    color: var(--accent-orange);
  }

  .optimal-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
</style>