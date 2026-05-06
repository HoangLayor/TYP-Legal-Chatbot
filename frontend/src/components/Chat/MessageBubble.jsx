import ReactMarkdown from "react-markdown";
import useVoice from "../../hooks/useVoice.js";
import formatTime from "../../utils/formatTime.js";
import Avatar from "../UI/Avatar.jsx";
import TypingIndicator from "./TypingIndicator.jsx";

export default function MessageBubble({ message }) {
  const isBot = message.role === "assistant";
  const isTyping = isBot && message.status === "typing" && !message.content;
  const isError = message.status === "error";
  const { speak, stopSpeaking, isSpeaking, isSpeechSynthesisSupported } = useVoice();

  function handleSpeak() {
    if (isSpeaking) {
      stopSpeaking();
      return;
    }
    speak(message.content);
  }

  return (
    <article className={`message-row ${message.role}`}>
      {isBot && <Avatar icon="⚖️" className="bot-avatar" />}
      <div className="message-stack">
        <div className={`message-bubble ${isError ? "error" : ""}`}>
          {isBot && !isTyping && message.content && isSpeechSynthesisSupported && (
            <button
              type="button"
              className={`bubble-speak-button ${isSpeaking ? "speaking" : ""}`}
              onClick={handleSpeak}
              aria-label="Đọc câu trả lời"
              title="Đọc câu trả lời"
            >
              <span className="icon-wrapper">🔈</span>
            </button>
          )}
          {isTyping ? (
            <TypingIndicator />
          ) : isBot ? (
            <ReactMarkdown>{message.content}</ReactMarkdown>
          ) : (
            <p>{message.content}</p>
          )}
        </div>
        <time>{formatTime(message.createdAt)}</time>
      </div>
    </article>
  );
}
