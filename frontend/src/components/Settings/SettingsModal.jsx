import SettingsTabs from "./SettingsTabs.jsx";

export default function SettingsModal({ onClose }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="settings-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="settings-header">
          <div>
            <h2 id="settings-title">Cài đặt</h2>
            <p>Tinh chỉnh trải nghiệm LegAI theo cách bạn làm việc.</p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Đóng cài đặt">
            <span className="icon-wrapper">✕</span>
          </button>
        </header>
        <SettingsTabs />
      </section>
    </div>
  );
}
