import UploadPanel from "./components/UploadPanel";
import ChatWindow from "./components/ChatWindow";
import "./App.css";

export default function App() {
  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <span className="logo-icon">🧠</span>
            <div>
              <h1 className="logo-title">RAG Agent</h1>
              <p className="logo-subtitle">Multi-LLM · RLHF</p>
            </div>
          </div>
        </div>
        <div className="sidebar-body">
          <UploadPanel />
        </div>
      </aside>

      {/* Main chat */}
      <main className="chat-area">
        <ChatWindow />
      </main>
    </div>
  );
}
