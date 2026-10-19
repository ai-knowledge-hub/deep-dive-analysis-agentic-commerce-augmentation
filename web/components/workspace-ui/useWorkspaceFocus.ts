import { useEffect } from "react";
export function useWorkspaceFocus(
  open: boolean,
  selector: string,
  close: () => void,
  trap = true,
) {
  useEffect(() => {
    if (!open) return;
    const before = document.activeElement as HTMLElement | null;
    const surface = document.querySelector<HTMLElement>(selector);
    if (!surface) return;
    const elements = () =>
      Array.from(
        surface.querySelectorAll<HTMLElement>(
          "button:not(:disabled), a[href], input, select, textarea, summary, [tabindex='0']",
        ),
      ).filter(
        (element) =>
          !element.closest("[inert], [hidden]") &&
          (element.tagName === "SUMMARY" ||
            !element.closest("details:not([open])")),
      );
    if (trap) surface.focus();
    function key(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
      if (event.key !== "Tab" || !trap) return;
      const items = elements();
      const first = items[0],
        last = items.at(-1);
      if (
        event.shiftKey &&
        (document.activeElement === first || document.activeElement === surface)
      ) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    surface.addEventListener("keydown", key);
    return () => {
      surface.removeEventListener("keydown", key);
      if (trap && before?.isConnected) {
        if (!before.closest("[inert]")) before.focus();
        else document.querySelector<HTMLElement>("[data-workspace-menu]")?.focus();
      }
    };
  }, [open, selector, close, trap]);
}
