import { useEffect, useMemo, useState } from "react";
import { Check, Mic, X } from "lucide-react";
import useVoice from "../../hooks/useVoice.js";

export default function STTPopup({ onCancel, onUseText }) {
  const { startListening, stopListening, isSpeechRecognitionSupported } = useVoice();
  const [finalText, setFinalText] = useState("");
  const [interimText, setInterimText] = useState("");

  const displayText = useMemo(() => [finalText, interimText].filter(Boolean).join(" ").trim(), [finalText, interimText]);

  useEffect(() => {
    if (!isSpeechRecognitionSupported) return undefined;

    startListening({
      continuous: true,
      onInterim: setInterimText,
      onResult: (text) => {
        setFinalText((current) => `${current ? `${current} ` : ""}${text}`);
        setInterimText("");
      },
    });

    return () => stopListening();
  }, []);

  function handleUseText() {
    if (displayText) onUseText(displayText);
    onCancel();
  }

  return (
    <section className="stt-popup" aria-label="Hỏi bằng giọng nói">
      <div className="stt-title">
        <Mic size={18} />
        <span>{isSpeechRecognitionSupported ? "Đang nghe..." : "Trình duyệt không hỗ trợ nhận giọng nói"}</span>
      </div>

      <div className="stt-visualizer" aria-hidden="true">
        {Array.from({ length: 7 }).map((_, index) => (
          <span key={index} />
        ))}
      </div>

      <textarea
        className="stt-transcript"
        readOnly
        value={displayText || (isSpeechRecognitionSupported ? "Văn bản nhận diện sẽ hiện ở đây..." : "Hãy thử Chrome hoặc Edge để dùng Web Speech API.")}
      />

      <div className="stt-actions">
        <button type="button" className="stt-cancel" onClick={onCancel}>
          <X size={16} />
          Hủy
        </button>
        <button type="button" className="stt-use" onClick={handleUseText} disabled={!displayText}>
          <Check size={16} />
          Dùng text
        </button>
      </div>
    </section>
  );
}
