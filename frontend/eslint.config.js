import js from "@eslint/js"
import { defineConfig, globalIgnores } from "eslint/config"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"
import globals from "globals"
import tseslint from "typescript-eslint"

export default defineConfig([
  // `src/types/api.ts` se genera con `pnpm gen:api`: no se edita ni se revisa.
  globalIgnores(["dist", "src/types/api.ts"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.strictTypeChecked,
      tseslint.configs.stylisticTypeChecked,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // Sin `any` (CLAUDE.md §10). strictTypeChecked ya lo prohíbe; se deja explícito.
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
    },
  },
  {
    // Componentes de shadcn/ui: código de terceros que no se modifica salvo
    // necesidad justificada (CLAUDE.md §4). Se relajan solo reglas de estilo y
    // la de fast refresh (exportan `buttonVariants`, `badgeVariants`…).
    files: ["src/components/ui/**/*.tsx"],
    rules: {
      "react-refresh/only-export-components": "off",
      "@typescript-eslint/array-type": "off",
      "@typescript-eslint/no-unnecessary-condition": "off",
    },
  },
  {
    // Scripts de Node (generación de tipos) y configuración en JS.
    files: ["**/*.{js,mjs}"],
    extends: [js.configs.recommended],
    languageOptions: { globals: globals.node },
  },
])
