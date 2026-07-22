import { defineConfig } from "vite";

export default defineConfig({
  plugins: [
    {
      name: "normalize-generated-whitespace",
      generateBundle(_options, bundle) {
        for (const output of Object.values(bundle)) {
          if (output.type === "chunk") {
            output.code = output.code.replace(
              /\[(\^?) \t\n\\f\\r/g,
              "[$1\\x20\\t\\n\\f\\r",
            );
          }
        }
      },
    },
  ],
  build: {
    emptyOutDir: true,
    lib: {
      entry: "src/index.ts",
      formats: ["es"],
      fileName: () => "irrigation-manager.js",
    },
    outDir: "dist",
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
      },
    },
  },
});
