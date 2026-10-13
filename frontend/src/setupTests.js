import "@testing-library/jest-dom/vitest";

// jsdom has no canvas backend; the 3D background guards on a null context.
// Stub it so tests stay quiet and deterministic.
if (typeof HTMLCanvasElement !== "undefined") {
  HTMLCanvasElement.prototype.getContext = () => null;
}
