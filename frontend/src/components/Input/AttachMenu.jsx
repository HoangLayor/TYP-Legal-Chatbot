import { Bot, Camera, Mic, Paperclip } from "lucide-react";

const menuItems = [
  { key: "attach", label: "Đính kèm tài liệu", icon: Paperclip },
  { key: "stt", label: "Hỏi bằng giọng nói", icon: Mic },
  { key: "live", label: "Trò chuyện với AI", icon: Bot },
  { key: "camera", label: "Chụp ảnh / Screenshot", icon: Camera },
];

export default function AttachMenu({ onSelect }) {
  return (
    <div className="attach-menu" role="menu">
      {menuItems.map((item) => {
        const Icon = item.icon;
        return (
          <button key={item.key} type="button" className="attach-menu-item" onClick={() => onSelect(item.key)}>
            <Icon size={18} strokeWidth={2.2} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}
