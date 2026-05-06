import useVoice from "../../hooks/useVoice.js";

export default function SpeakButton({ text = "", label = "Đọc nội dung", icon = "🔊", className = "" }) {
  const { speak, stopSpeaking, isSpeaking, isSpeechSynthesisSupported } = useVoice();
  const isDisabled = !isSpeechSynthesisSupported || !text.trim();

  function handleClick() {
    if (isDisabled) return;
    if (isSpeaking) {
      stopSpeaking();
      return;
    }
    speak(text);
  }

  return (
    <button
      type="button"
      className={`speak-button ${className} ${isSpeaking ? "speaking" : ""}`}
      onClick={handleClick}
      disabled={isDisabled}
      aria-label={label}
      title={label}
    >
      <span className="icon-wrapper">{icon}</span>
    </button>
  );
}
