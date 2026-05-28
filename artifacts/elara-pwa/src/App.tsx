import React from "react";
import { AppProvider, useApp } from "@/contexts/AppContext";
import LoginPage from "@/pages/LoginPage";
import ChatPage from "@/pages/ChatPage";

function Router() {
  const { page } = useApp();
  if (page === "login") return <LoginPage />;
  return <ChatPage />;
}

export default function App() {
  return (
    <AppProvider>
      <Router />
    </AppProvider>
  );
}
