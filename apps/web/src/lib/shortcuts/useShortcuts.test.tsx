import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useShortcuts, type ShortcutHandlers } from "./useShortcuts";

// tinykeys ignores events without both `key` and `code`, as real keyboards always send.
function press(target: Element, key: string, init: KeyboardEventInit = {}) {
  const code = /^[a-z]$/i.test(key) ? `Key${key.toUpperCase()}` : key === "?" ? "Slash" : key;
  return fireEvent.keyDown(target, { key, code, ...init });
}

function Screening({ handlers }: { handlers: ShortcutHandlers<"screening"> }) {
  useShortcuts("screening", handlers);
  return (
    <div>
      <input aria-label="note" />
      <textarea aria-label="long note" />
      <div contentEditable aria-label="editor" />
      <button type="button">plain</button>
      <div role="dialog">
        <button type="button">in dialog</button>
      </div>
    </div>
  );
}

function Help({ onHelp }: { onHelp: () => void }) {
  useShortcuts("global", { help: onHelp });
  return (
    <div role="dialog">
      <button type="button">in dialog</button>
    </div>
  );
}

describe("useShortcuts", () => {
  it("runs the handler of a bound key, in either case", () => {
    const include = vi.fn();
    render(<Screening handlers={{ include }} />);

    press(document.body, "i");
    press(document.body, "I");

    expect(include).toHaveBeenCalledTimes(2);
  });

  it("is silent while typing in a text field", () => {
    const include = vi.fn();
    const { getByLabelText } = render(<Screening handlers={{ include }} />);

    for (const field of ["note", "long note", "editor"]) {
      press(getByLabelText(field), "i");
    }

    expect(include).not.toHaveBeenCalled();
  });

  it("still answers on a focused button", () => {
    const include = vi.fn();
    const { getByText } = render(<Screening handlers={{ include }} />);

    press(getByText("plain"), "i");

    expect(include).toHaveBeenCalledOnce();
  });

  it("keeps a screen's keys quiet inside a dialog, but not the global ones", () => {
    const include = vi.fn();
    const help = vi.fn();
    const { getAllByText } = render(
      <>
        <Screening handlers={{ include }} />
        <Help onHelp={help} />
      </>,
    );
    const [screeningDialog, helpDialog] = getAllByText("in dialog");

    press(screeningDialog as Element, "i");
    press(helpDialog as Element, "?", { shiftKey: true });

    expect(include).not.toHaveBeenCalled();
    expect(help).toHaveBeenCalledOnce();
  });

  it("binds only the shortcuts given a handler, and lets go on unmount", () => {
    const include = vi.fn();
    const view = render(<Screening handlers={{ include }} />);

    const skipped = press(document.body, "ArrowRight");
    view.unmount();
    press(document.body, "i");

    expect(skipped).toBe(true); // not prevented: the browser keeps the key
    expect(include).not.toHaveBeenCalled();
  });

  it("uses the latest handler without binding again", () => {
    const first = vi.fn();
    const second = vi.fn();
    const view = render(<Screening handlers={{ include: first }} />);
    view.rerender(<Screening handlers={{ include: second }} />);

    press(document.body, "i");

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledOnce();
  });
});
