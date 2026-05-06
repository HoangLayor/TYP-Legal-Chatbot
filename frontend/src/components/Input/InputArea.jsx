import { useEffect, useRef, useState } from "react";
import { Plus, Send, Volume2 } from "lucide-react";
import { useChatContext } from "../../context/ChatContext.jsx";
import useChat from "../../hooks/useChat.js";
import LiveChatPopup from "../Voice/LiveChatPopup.jsx";
import STTPopup from "../Voice/STTPopup.jsx";
import AttachMenu from "./AttachMenu.jsx";
import ChatTextarea from "./ChatTextarea.jsx";
import SpeakButton from "./SpeakButton.jsx";

export default function InputArea({ draft, onDraftChange }) {
  const [localDraft, setLocalDraft] = useState("");
  const [isAttachMenuOpen, setIsAttachMenuOpen] = useState(false);
  const [isSTTOpen, setIsSTTOpen] = useState(false);
  const [isLiveChatOpen, setIsLiveChatOpen] = useState(false);
  const attachRef = useRef(null);
  const { sendMessage, isSending } = useChat();
  const { activeConversation } = useChatContext();
  const value = draft ?? localDraft;
  const setValue = onDraftChange ?? setLocalDraft;
  const latestAssistantAnswer =
    activeConversation?.messages
      ?.filter((message) => message.role === "assistant" && message.content)
      .at(-1)?.content || "";

  async function handleSubmit(event) {
    event?.preventDefault();
    const message = value.trim();
    if (!message || isSending) return;
    setValue("");
    await sendMessage(message);
  }

  function appendTranscript(transcript) {
    setValue((current) => {
      const prefix = current.trim() ? `${current.trim()} ` : "";
      return `${prefix}${transcript}`;
    });
  }

  function handleAttachAction(action) {
    setIsAttachMenuOpen(false);
    if (action === "stt") setIsSTTOpen(true);
    if (action === "live") setIsLiveChatOpen(true);
  }

  useEffect(() => {
    function handleOutsideClick(event) {
      if (attachRef.current && !attachRef.current.contains(event.target)) {
        setIsAttachMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  return (
    <form className="input-area" onSubmit={handleSubmit}>
      {isSTTOpen && <STTPopup onCancel={() => setIsSTTOpen(false)} onUseText={appendTranscript} />}
      {isLiveChatOpen && <LiveChatPopup onClose={() => setIsLiveChatOpen(false)} />}

      <div className="composer-shell input-wrapper">
        <div className="attach-trigger" ref={attachRef}>
          <button
            type="button"
            className={`input-btn attach-plus-button ${isAttachMenuOpen ? "open" : ""}`}
            onClick={() => setIsAttachMenuOpen((current) => !current)}
            aria-label="Mở menu tính năng"
          >
            <Plus size={20} />
          </button>
          {isAttachMenuOpen && <AttachMenu onSelect={handleAttachAction} />}
        </div>
        <ChatTextarea value={value} onChange={setValue} onSubmit={handleSubmit} />
        <SpeakButton text={latestAssistantAnswer} label="Đọc câu trả lời gần nhất" icon={<Volume2 size={18} />} className="answer-speaker input-btn" />
        <button className={`send-button input-btn ${isSending ? "loading" : ""}`} type="submit" disabled={!value.trim() || isSending} aria-label="Gửi tin nhắn">
          <Send size={18} />
        </button>
      </div>
      <p>LegAI có thể mắc lỗi. Vui lòng xác minh thông tin pháp lý với chuyên gia.</p>
    </form>
  );
}
