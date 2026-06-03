import next from "eslint-config-next";

/**
 * Flat ESLint config for Next.js 16. `eslint-config-next` exports a flat-config
 * array directly, so it can be spread without the legacy FlatCompat bridge.
 */
const eslintConfig = [
  ...next,
  {
    ignores: ["out/**", ".next/**", "node_modules/**"],
  },
];

export default eslintConfig;
