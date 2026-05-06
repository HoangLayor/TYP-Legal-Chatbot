import useVoice from "../../hooks/useVoice.js";

export default function VoiceButton({ onTranscript }) {
  const { startListening, stopListening, isListening, isSpeechRecognitionSupported } = useVoice();

  if (!isSpeechRecognitionSupported) return null;

  function handleClick() {
    if (isListening) {
      stopListening();
      return;
    }
    startListening(onTranscript);
  }

  return (
    <button
      type="button"
      className={`voice-button ${isListening ? "listening" : ""}`}
      onClick={handleClick}
      aria-label={isListening ? "Đang nghe..." : "Nhập bằng giọng nói"}
      title={isListening ? "Đang nghe..." : "Nhập bằng giọng nói"}
    >
      <span className="icon-wrapper">🎤</span>
    </button>
  );
}
