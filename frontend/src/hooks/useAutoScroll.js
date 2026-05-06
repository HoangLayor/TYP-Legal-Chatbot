import { useEffect, useRef } from "react";

export default function useAutoScroll(dependencies = []) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, dependencies);

  return bottomRef;
}
