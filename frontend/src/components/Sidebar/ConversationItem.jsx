import Tooltip from "../UI/Tooltip.jsx";

export default function ConversationItem({ conversation, isActive, onSelect, onDelete }) {
  function handleKeyDown(event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect();
    }
  }

  return (
    <Tooltip label={conversation.title}>
      <div
        className={`conversation-item ${isActive ? "active" : ""}`}
        role="button"
        tabIndex={0}
        onClick={onSelect}
        onKeyDown={handleKeyDown}
      >
        <span className="conversation-icon icon-wrapper">💬</span>
        <span className="conversation-title">{conversation.title}</span>
        <button
          className="conversation-delete"
          type="button"
          aria-label="Xóa cuộc trò chuyện"
          onClick={(event) => {
            event.stopPropagation();
            onDelete();
          }}
        >
          <span className="icon-wrapper">🗑️</span>
        </button>
      </div>
    </Tooltip>
  );
}
