import adapter from "@sveltejs/adapter-static";
import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

const isDev = !process.env.BASE_PATH;

export default defineConfig({
  plugins: [
    sveltekit({
      compilerOptions: {
        runes: ({ filename }: { filename: string }) =>
          filename.split(/[/\\]/).includes("node_modules") ? undefined : true,
      },
      adapter: adapter({
        pages: "build",
        assets: "build",
        fallback: "404.html",
      }),
      paths: {
        base: isDev ? "" : (process.env.BASE_PATH ?? ""),
      },
    }),
  ],
});
