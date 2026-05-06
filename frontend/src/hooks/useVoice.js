import { useEffect, useRef, useState } from "react";

function getSpeechRecognition() {
  return window.SpeechRecognition || window.webkitSpeechRecognition;
}

function stripMarkdown(text) {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/#{1,6}\s*/g, "")
    .replace(/[*_~>]/g, "")
    .replace(/^\s*[-+]\s+/gm, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

export default function useVoice() {
  const recognitionRef = useRef(null);
  const utteranceRef = useRef(null);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const isSpeechRecognitionSupported = typeof window !== "undefined" && Boolean(getSpeechRecognition());
  const isSpeechSynthesisSupported = typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      window.speechSynthesis?.cancel();
    };
  }, []);

  function startListening(options) {
    if (!isSpeechRecognitionSupported) return;

    const handlers = typeof options === "function" ? { onResult: options } : options || {};
    const SpeechRecognition = getSpeechRecognition();
    const recognition = recognitionRef.current || new SpeechRecognition();
    recognitionRef.current = recognition;

    recognition.lang = "vi-VN";
    recognition.interimResults = Boolean(handlers.onInterim);
    recognition.continuous = Boolean(handlers.continuous);

    recognition.onresult = (event) => {
      let finalTranscript = "";
      let interimTranscript = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const transcript = event.results[index][0]?.transcript || "";
        if (event.results[index].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      if (interimTranscript.trim()) handlers.onInterim?.(interimTranscript.trim());
      if (finalTranscript.trim()) handlers.onResult?.(finalTranscript.trim());
    };

    recognition.onend = () => {
      setIsListening(false);
      handlers.onEnd?.();
    };
    recognition.onerror = () => {
      setIsListening(false);
      handlers.onError?.();
    };

    try {
      setIsListening(true);
      recognition.start();
    } catch {
      setIsListening(false);
    }
  }

  function stopListening() {
    try {
      recognitionRef.current?.stop();
    } catch {
      setIsListening(false);
    }
    setIsListening(false);
  }

  function speak(text) {
    if (!isSpeechSynthesisSupported) return;

    const readableText = stripMarkdown(text);
    if (!readableText) return;

    if (isSpeaking) {
      stopSpeaking();
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(readableText);
    utterance.lang = "vi-VN";
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    utteranceRef.current = utterance;
    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  function stopSpeaking() {
    window.speechSynthesis?.cancel();
    utteranceRef.current = null;
    setIsSpeaking(false);
  }

  return {
    startListening,
    stopListening,
    isListening,
    speak,
    stopSpeaking,
    isSpeaking,
    isSpeechRecognitionSupported,
    isSpeechSynthesisSupported,
  };
}
