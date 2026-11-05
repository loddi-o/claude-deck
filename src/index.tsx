import { definePlugin, routerHook } from "@decky/api";
import { DialogButton, ErrorBoundary, staticClasses } from "@decky/ui";
import { FaCog } from "react-icons/fa";
import { Spark } from "./components/ui";
import { FullScreen } from "./pages/FullScreen";
import { QuickPanel } from "./pages/QuickPanel";
import { ROUTE, disposeStore, initStore, openSettings } from "./store";

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
    titleView: (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
        <div className={staticClasses.Title}>Claude Deck</div>
        <DialogButton
          style={{ height: "28px", width: "40px", minWidth: 0, padding: "10px 12px" }}
          onClick={openSettings}
        >
          <FaCog />
        </DialogButton>
      </div>
    ),
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
