// Cloud Settings embed build.
//
// Ships a classic-script IIFE so Desk can `<script src>` it cross-origin with no
// CORS and no Pilot credentials. The dialog renders inside a shadow root, so all
// CSS (Tailwind + frappe-ui) is inlined into the JS and adopted into that root —
// there is no separate stylesheet and no selector-scoping hack.
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import frappeuiPlugin from "frappe-ui/vite";
import path from "path";
import fs from "fs";

export default defineConfig({
  plugins: [
    frappeuiPlugin({
      lucideIcons: true,
      frappeProxy: false,
      jinjaBootData: false,
      buildConfig: false,
    }),
    // `customElement` keeps SFC styles out of <head> so they land in the shadow root.
    vue({ customElement: true }),
    // Every style is already inlined into the JS (Tailwind via `?inline`, SFC
    // styles via customElement mode), so the stylesheet Vite extracts alongside
    // it is dead weight nothing loads. Drop it so the shipped bundle is one file.
    // (rolldown ignores deletions from the generateBundle map, hence the unlink.)
    {
      name: "cloud-settings-drop-css-assets",
      closeBundle() {
        const dir = path.resolve(__dirname, "../backend/static/dist/embed/cloud-settings/assets");
        if (!fs.existsSync(dir)) return;
        for (const file of fs.readdirSync(dir)) {
          if (file.endsWith(".css")) fs.rmSync(path.join(dir, file));
        }
        if (!fs.readdirSync(dir).length) fs.rmdirSync(dir);
      },
    },
  ],
  resolve: {
    alias: {
      // frappe-ui marks every .vue as having side effects, so importing from the
      // package barrel defeats tree-shaking and pulls in the editor, charts and
      // their dynamic imports (3.1 MB, and dynamic imports make IIFE impossible).
      // Deep-importing each component keeps the bundle small and IIFE-able; the
      // exports map has no ./src/* wildcard, hence this alias.
      "frappe-ui/src": path.resolve(__dirname, "node_modules/frappe-ui/src"),
    },
  },
  build: {
    outDir: "../backend/static/dist/embed/cloud-settings",
    emptyOutDir: true,
    cssCodeSplit: false,
    sourcemap: false,
    minify: true,
    // Inline the gateway logos so the bundle is a single self-contained file and
    // no asset URL has to resolve against the Desk site's origin.
    assetsInlineLimit: 1024 * 1024,
    rolldownOptions: {
      input: path.resolve(__dirname, "src/embed/cloud-settings/index.js"),
      output: {
        format: "iife",
        name: "FrappeCloudSettingsEmbed",
        entryFileNames: "cloud-settings.js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
