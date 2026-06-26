<script>
  import { base } from "$app/paths";
  let { children } = $props();
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet" />
</svelte:head>

<div class="layout">
  <nav class="top-nav">
    <a href={base + "/"} class="logo">mcph</a>
    <div class="nav-links">
      <a href={base + "/architecture/"}>Architecture</a>
      <a href={base + "/phases/"}>Phases</a>
      <a href={base + "/api/"}>API</a>
      <a href="https://github.com/rmax-ai/mcph" class="gh-link">GitHub ↗</a>
    </div>
  </nav>
  <main>{@render children()}</main>
</div>

<style>
  :global(*) {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  :global(body) {
    background: #020617;
    color: #e2e8f0;
    font-family: "Inter", system-ui, sans-serif;
    line-height: 1.7;
  }

  :global(h1, h2, h3, h4) {
    font-family: "JetBrains Mono", monospace;
    color: #f1f5f9;
  }

  :global(h1) { font-size: 2rem; margin-bottom: 1rem; }
  :global(h2) { font-size: 1.4rem; margin: 2rem 0 0.75rem; color: #22d3ee; }
  :global(h3) { font-size: 1.1rem; margin: 1.5rem 0 0.5rem; }
  :global(p) { margin-bottom: 1rem; color: #94a3b8; }
  :global(a) { color: #22d3ee; text-decoration: none; }
  :global(a:hover) { text-decoration: underline; }
  :global(code) {
    font-family: "JetBrains Mono", monospace;
    background: rgba(30, 41, 59, 0.5);
    padding: 0.15em 0.4em;
    border-radius: 4px;
    font-size: 0.9em;
    color: #e2e8f0;
  }
  :global(pre) {
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 1rem;
    overflow-x: auto;
    margin-bottom: 1rem;
  }
  :global(pre code) {
    background: none;
    padding: 0;
  }
  :global(ul, ol) { margin: 0.5rem 0 1rem 1.5rem; color: #94a3b8; }
  :global(li) { margin-bottom: 0.25rem; }
  :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
  }
  :global(th, td) {
    border: 1px solid #1e293b;
    padding: 0.5rem 0.75rem;
    text-align: left;
    font-size: 0.9rem;
  }
  :global(th) { background: rgba(30, 41, 59, 0.5); color: #e2e8f0; }
  :global(td) { color: #94a3b8; }

  .layout {
    min-height: 100vh;
  }

  .top-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    border-bottom: 1px solid #1e293b;
    background: rgba(2, 6, 23, 0.8);
    backdrop-filter: blur(12px);
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .logo {
    font-family: "JetBrains Mono", monospace;
    font-weight: 700;
    font-size: 1.2rem;
    color: #22d3ee !important;
    text-decoration: none !important;
  }

  .nav-links {
    display: flex;
    gap: 1.5rem;
  }

  .nav-links a {
    color: #94a3b8;
    font-size: 0.9rem;
    transition: color 0.15s;
  }

  .nav-links a:hover {
    color: #e2e8f0;
    text-decoration: none;
  }

  .gh-link {
    color: #22d3ee !important;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.85rem;
  }

  main {
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem;
  }
</style>
