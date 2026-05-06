import { useChatContext } from "../../context/ChatContext.jsx";
import ThemeToggle from "../UI/ThemeToggle.jsx";

export default function TopBar({ onOpenSidebar }) {
  const { activeConversation } = useChatContext();

  return (
    <header className="topbar">
      <button className="hamburger-button" onClick={onOpenSidebar} aria-label="Mở menu">
        ☰
      </button>
      <h1>{activeConversation?.title || "Cuộc trò chuyện mới"}</h1>
      <ThemeToggle />
    </header>
  );
}
