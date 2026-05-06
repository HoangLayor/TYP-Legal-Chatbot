import { Settings } from "lucide-react";
import Avatar from "../UI/Avatar.jsx";

export default function SidebarFooter({ onOpenSettings }) {
  return (
    <footer className="sidebar-footer">
      <Avatar label="Người dùng" variant="user" />
      <div className="user-info">
        <span className="user-name">Người dùng</span>
        <span className="user-status">
          <span className="dot" />
          Online
        </span>
      </div>
      <button className="settings-btn" onClick={onOpenSettings} aria-label="Mở cài đặt">
        <Settings size={18} />
      </button>
    </footer>
  );
}
