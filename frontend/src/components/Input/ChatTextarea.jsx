import { useEffect, useRef } from "react";

export default function ChatTextarea({ value, onChange, onSubmit }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 138)}px`;
  }, [value]);

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <textarea
      className="chat-textarea"
      ref={textareaRef}
      value={value}
      rows={1}
      placeholder="Nhập câu hỏi pháp lý của bạn..."
      onChange={(event) => onChange(event.target.value)}
      onKeyDown={handleKeyDown}
    />
  );
}
