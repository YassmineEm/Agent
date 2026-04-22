"use client";
import { useEffect } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/hooks/useAuth";
import { useChatStore, GUEST_CHATBOT_NAME } from "@/stores/chatStore";
import Chat from "./pages/Chat";
import Auth from "./pages/Auth";
import History from "./pages/History";
import NotFound from "./pages/NotFound";
import { ThemeProvider } from "next-themes";

const queryClient = new QueryClient();

const AppContent = () => {
  const { isGuest, user } = useAuth(); 
  const { loadChatbots, loadConversations, setActiveChatbot } = useChatStore(); 

  // Chargement initial des chatbots + Polling + Visibility API
  useEffect(() => {
    // 1. Chargement initial avec userId
    loadChatbots(isGuest, user?.id);

    // 2. Polling toutes les 30 secondes
    const interval = setInterval(() => {
      loadChatbots(isGuest, user?.id);
    }, 30_000);

    // 3. Visibility API : recharge dès que l'onglet redevient actif
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        loadChatbots(isGuest, user?.id);
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);

    // 4. Nettoyage
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isGuest, user?.id]); 

 
  useEffect(() => {
    if (!isGuest && user?.id) {
      loadConversations(user.id);
    }
  }, [isGuest, user?.id, loadConversations]);

  // Recalage quand l'utilisateur se déconnecte → revenir sur Afriquia
  useEffect(() => {
    if (isGuest) {
      setActiveChatbot(GUEST_CHATBOT_NAME);
    }
  }, [isGuest, setActiveChatbot]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/auth" element={<Auth />} />
        <Route path="/history" element={<History />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
};

const App = () => {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <TooltipProvider>
            <Toaster />
            <Sonner />
            <AppContent />
          </TooltipProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
};

export default App;