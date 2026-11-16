import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// `findBy…` and `waitFor` wait 1 s by default. `pnpm check` runs the backend tests on every
// core beside these, and on a busy machine a screen can take longer than that to settle;
// waiting longer changes nothing a test asserts, only how long it may take to get there.
configure({ asyncUtilTimeout: 5_000 });

afterEach(() => {
  cleanup();
});
