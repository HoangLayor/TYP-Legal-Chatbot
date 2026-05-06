import Tooltip from "../UI/Tooltip.jsx";

export default function NewChatButton({ onClick }) {
  return (
    <Tooltip label="Cuộc trò chuyện mới">
      <button className="new-chat-button" onClick={onClick}>
        <span className="new-chat-plus icon-wrapper">+</span>
        <span className="new-chat-label">Cuộc trò chuyện mới</span>
      </button>
    </Tooltip>
  );
}
