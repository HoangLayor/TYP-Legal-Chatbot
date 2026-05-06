import { useState } from "react";
import { useTheme } from "../../context/ThemeContext.jsx";

export default function SettingsTabs() {
  const [tab, setTab] = useState("appearance");
  const { theme, setTheme, toggleTheme } = useTheme();

  return (
    <div className="settings-content">
      <nav className="settings-tabs" aria-label="Cài đặt">
        <button className={tab === "appearance" ? "active" : ""} onClick={() => setTab("appearance")}>
          Giao diện
        </button>
        <button className={tab === "language" ? "active" : ""} onClick={() => setTab("language")}>
          Ngôn ngữ
        </button>
        <button className={tab === "info" ? "active" : ""} onClick={() => setTab("info")}>
          Thông tin
        </button>
      </nav>

      <section className="settings-panel">
        {tab === "appearance" && (
          <>
            <div className="setting-row">
            <div>
              <strong>Chế độ giao diện</strong>
              <span>Chuyển đổi sáng tối với animation mượt.</span>
            </div>
            <button
              type="button"
              className={`settings-theme-toggle ${theme === "dark" ? "is-dark" : ""}`}
              onClick={toggleTheme}
              aria-label="Đổi giao diện sáng tối"
            >
              <span />
            </button>
          </div>
            <div className="setting-row">
              <div>
                <strong>Theme nhanh</strong>
                <span>Chọn trực tiếp bảng màu bạn muốn dùng.</span>
              </div>
              <div className="segmented-control">
                <button className={theme === "light" ? "active" : ""} onClick={() => setTheme("light")}>
                  Sáng
                </button>
                <button className={theme === "dark" ? "active" : ""} onClick={() => setTheme("dark")}>
                  Tối
                </button>
              </div>
            </div>
          </>
        )}

        {tab === "language" && (
          <div className="setting-row">
            <div>
              <strong>Ngôn ngữ</strong>
              <span>Giao diện hiện tối ưu cho tiếng Việt.</span>
            </div>
            <div className="segmented-control">
              <button className="active">Tiếng Việt</button>
              <button>English</button>
            </div>
          </div>
        )}

        {tab === "info" && (
          <div className="info-grid">
            <div>
              <span>Phiên bản</span>
              <strong>LegAI 0.2.0</strong>
            </div>
            <div>
              <span>Hỗ trợ</span>
              <strong>support@legai.local</strong>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
