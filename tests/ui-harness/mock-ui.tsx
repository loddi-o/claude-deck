/* Minimal stand-ins for @decky/ui so the real plugin components can render in a normal browser. */
import React, { ReactNode, useState } from "react";

const STEAM_PROPS = new Set([
  "focusClassName", "focusWithinClassName", "noFocusRing", "flow-children", "onActivate", "onCancel",
  "onOKActionDescription", "onCancelActionDescription", "onSecondaryActionDescription", "onOptionsActionDescription",
  "onMenuActionDescription", "onButtonDown", "onButtonUp", "onOKButton", "onCancelButton", "onSecondaryButton",
  "onOptionsButton", "onGamepadDirection", "onGamepadFocus", "onGamepadBlur", "onMenuButton", "preferredFocus",
  "actionDescriptionMap", "navEntryPreferPosition", "focusable", "layout", "bIsPassword", "focusOnMount",
]);

function clean(props: Record<string, any>) {
  const out: Record<string, any> = {};
  for (const [k, v] of Object.entries(props)) if (!STEAM_PROPS.has(k)) out[k] = v;
  return out;
}

export enum GamepadButton { BUMPER_LEFT = 5, BUMPER_RIGHT = 6 }

export function Focusable({ children, className = "", focusClassName, onActivate, onClick, ...rest }: any) {
  const [f, setF] = useState(false);
  return (
    <div
      {...clean(rest)}
      tabIndex={0}
      className={`${className} ${f ? "gpfocus " + (focusClassName ?? "") : ""}`}
      onFocus={() => setF(true)}
      onBlur={() => setF(false)}
      onClick={(e) => (onActivate ?? onClick)?.(e)}
    >
      {children}
    </div>
  );
}

export function DialogButton({ children, className = "", onClick, disabled, ...rest }: any) {
  const [f, setF] = useState(false);
  return (
    <button
      {...clean(rest)}
      disabled={disabled}
      className={`DialogButton ${className} ${f ? "gpfocus" : ""}`}
      onFocus={() => setF(true)}
      onBlur={() => setF(false)}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

export const DialogHeader = ({ children }: any) => <h3>{children}</h3>;
export const DialogFooter = ({ children }: any) => <div style={{ display: "flex", gap: 8 }}>{children}</div>;
export const ModalRoot = ({ children }: any) => <div className="mock-modal">{children}</div>;
export const ConfirmModal = ({ strTitle, strDescription }: any) => <div className="mock-modal">{strTitle}{strDescription}</div>;
export const showModal = () => ({ Close() {}, ClosedPromise: Promise.resolve(), Update() {} });
export const ErrorBoundary = ({ children }: any) => <>{children}</>;
export const staticClasses = { Title: "mock-title" };

export function TextField({ value, onChange, placeholder, onKeyDown, bIsPassword }: any) {
  return (
    <input
      className="mock-input"
      type={bIsPassword ? "password" : "text"}
      value={value ?? ""}
      placeholder={placeholder}
      onChange={onChange}
      onKeyDown={onKeyDown}
    />
  );
}

export function PanelSection({ title, children }: { title?: string; children?: ReactNode }) {
  return (
    <div className="mock-section">
      {title && <div className="mock-section-title">{title}</div>}
      {children}
    </div>
  );
}
export const PanelSectionRow = ({ children }: any) => <div className="mock-row">{children}</div>;

export function ButtonItem({ children, onClick, disabled }: any) {
  return (
    <button className="DialogButton mock-buttonitem" onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

export function ToggleField({ label, checked, onChange }: any) {
  return (
    <label className="mock-field">
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange?.(e.target.checked)} />
    </label>
  );
}

export function DropdownItem({ label, rgOptions, selectedOption, onChange }: any) {
  return (
    <label className="mock-field">
      <span>{label}</span>
      <select value={selectedOption} onChange={(e) => onChange?.(rgOptions.find((o: any) => String(o.data) === e.target.value))}>
        {rgOptions.map((o: any) => (
          <option key={String(o.data)} value={o.data}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SliderField({ label, value, min, max, step, onChange, valueSuffix }: any) {
  return (
    <label className="mock-field">
      <span>
        {label} <b>{value}{valueSuffix}</b>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange?.(Number(e.target.value))} />
    </label>
  );
}

export const Navigation = {
  Navigate() {}, NavigateBack() {}, CloseSideMenus() {}, NavigateToExternalWeb() {},
};
