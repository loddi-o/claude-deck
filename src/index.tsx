import { definePlugin, routerHook } from "@decky/api";
import { ErrorBoundary, staticClasses } from "@decky/ui";
import { Spark } from "./components/ui";
import { FullScreen } from "./pages/FullScreen";
import { QuickPanel } from "./pages/QuickPanel";
import { ROUTE, disposeStore, initStore } from "./store";

export default definePlugin(() => {
  // The store lives as long as the plugin so a running conversation survives closing the QAM.
  void initStore();

  routerHook.addRoute(
    ROUTE,
    () => (
      <ErrorBoundary>
        <FullScreen />
      </ErrorBoundary>
    ),
    { exact: true }
  );

  return {
    name: "Claude Deck",
    titleView: <div className={staticClasses.Title}>Claude Deck</div>,
    content: (
      <ErrorBoundary>
        <QuickPanel />
      </ErrorBoundary>
    ),
    icon: <Spark size={22} />,
    onDismount() {
      routerHook.removeRoute(ROUTE);
      disposeStore();
    },
  };
});
