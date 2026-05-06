import { useTheme } from "../../context/ThemeContext.jsx";

export default function ThemeToggle() {
  const { isDark, toggleTheme } = useTheme();

  return (
    <button className={`theme-toggle ${isDark ? "is-dark" : "is-light"}`} onClick={toggleTheme} aria-label="Đổi giao diện sáng tối">
      <span className="theme-toggle-track">
        <span className="theme-toggle-thumb">{isDark ? "🌙" : "☀️"}</span>
      </span>
    </button>
  );
}
