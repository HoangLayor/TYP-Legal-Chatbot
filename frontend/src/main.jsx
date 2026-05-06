import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles/themes.css";
import "./styles/animations.css";
import "./styles/global.css";
import "./styles/stt-popup.css";
import "./styles/livechat-popup.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
