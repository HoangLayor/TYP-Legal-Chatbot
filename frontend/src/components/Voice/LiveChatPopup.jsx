import { useState } from "react";
import { Bot, Mic, Square, X } from "lucide-react";
import useChat from "../../hooks/useChat.js";
import useVoice from "../../hooks/useVoice.js";

export default function LiveChatPopup({ onClose }) {
  const { sendMessage, isSending } = useChat();
  const { startListening, stopListening, speak, stopSpeaking, isListening, isSpeaking, isSpeechRecognitionSupported } = useVoice();
  const [transcript, setTranscript] = useState("");
  const [status, setStatus] = useState("idle");

  async function handleResult(text) {
    if (!text) return;
    setTranscript(text);
    setStatus("thinking");
    const reply = await sendMessage(text);
    setStatus("speaking");
    speak(reply || "");
  }

  function startHoldToTalk() {
    if (!isSpeechRecognitionSupported || isSending) return;
    stopSpeaking();
    setTranscript("");
    setStatus("listening");
    startListening({
      onInterim: setTranscript,
      onResult: handleResult,
      onEnd: () => setStatus((current) => (current === "listening" ? "idle" : current)),
    });
  }

  function stopHoldToTalk() {
    stopListening();
  }

  function handleClose() {
    stopListening();
    stopSpeaking();
    onClose();
  }

  const statusLabel = status === "thinking" || isSending ? "Đang trả lời" : isSpeaking ? "Đang nói" : "Đang lắng nghe";

  return (
    <div className="livechat-overlay" role="presentation">
      <section className="livechat-popup" role="dialog" aria-modal="true" aria-label="Trò chuyện trực tiếp">
        <header className="livechat-header">
          <div>
            <Bot size={20} />
            <span>Trò chuyện trực tiếp</span>
          </div>
          <button type="button" onClick={handleClose} aria-label="Đóng trò chuyện trực tiếp">
            <X size={18} />
          </button>
        </header>

        <div className={`livechat-avatar ${isSpeaking || status === "thinking" ? "active" : ""}`}>
          <Bot size={42} />
        </div>

        <div className={`livechat-status ${status === "thinking" || isSpeaking ? "answering" : ""}`}>
          <span />
          {isSpeechRecognitionSupported ? statusLabel : "Trình duyệt không hỗ trợ STT"}
        </div>

        <div className="livechat-transcript">{transcript || "Bạn vừa nói gì hiện ở đây..."}</div>

        <button
          type="button"
          className="hold-talk-button"
          onMouseDown={startHoldToTalk}
          onMouseUp={stopHoldToTalk}
          onMouseLeave={stopHoldToTalk}
          onTouchStart={startHoldToTalk}
          onTouchEnd={stopHoldToTalk}
          disabled={!isSpeechRecognitionSupported || isSending}
        >
          <Mic size={18} />
          {isListening ? "Đang nghe..." : "Giữ để nói"}
        </button>

        <button type="button" className="end-session-button" onClick={handleClose}>
          <Square size={14} />
          Kết thúc phiên
        </button>
      </section>
    </div>
  );
}
