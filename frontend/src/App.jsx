import { useState } from "react";
import { ChatProvider } from "./context/ChatContext.jsx";
import { ThemeProvider } from "./context/ThemeContext.jsx";
import ChatLayout from "./components/Chat/ChatLayout.jsx";
import Sidebar from "./components/Sidebar/Sidebar.jsx";
import SettingsModal from "./components/Settings/SettingsModal.jsx";

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  return (
    <ThemeProvider>
      <ChatProvider>
        <div className="app-shell">
          <Sidebar
            isOpen={isSidebarOpen}
            onClose={() => setIsSidebarOpen(false)}
            onOpenSettings={() => setIsSettingsOpen(true)}
          />
          <ChatLayout onOpenSidebar={() => setIsSidebarOpen(true)} />
          {isSettingsOpen && <SettingsModal onClose={() => setIsSettingsOpen(false)} />}
        </div>
      </ChatProvider>
    </ThemeProvider>
  );
}

export default App;
