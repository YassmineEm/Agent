import { useState, useRef, useEffect } from "react";
import { Send, Trash2, Sparkles, Lock, LogIn, UserPlus, MapPin } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useChatStore } from "@/stores/chatStore";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import WelcomeScreen from "@/components/chat/WelcomeScreen";
import MessageBubble from "@/components/chat/MessageBubble";
import { sendMessage } from "@/services/api";
import { ThemeToggle } from "@/components/ThemeToggle";

const GUEST_MESSAGE_LIMIT = 5;

const ChatArea = () => {
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [guestMessageCount, setGuestMessageCount] = useState(0);
  const [geoStatus, setGeoStatus] = useState<"idle" | "requesting" | "granted" | "denied">("idle");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { isGuest, sessionId, user } = useAuth();
  const { toast } = useToast();

  const {
    chatbots,
    activeChatbotName,
    activeConversationId,
    conversations,
    addMessage,
    clearConversation,
    createConversation,
  } = useChatStore();

  const activeChatbot = chatbots.find((c) => c.name === activeChatbotName);
  const activeConversation = conversations.find((c) => c.id === activeConversationId);
  const messages = activeConversation?.messages ?? [];

  const isGuestLimitReached = isGuest && guestMessageCount >= GUEST_MESSAGE_LIMIT;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  useEffect(() => {
    if (geoStatus === "granted" || geoStatus === "denied") {
      const timer = setTimeout(() => setGeoStatus("idle"), 3000);
      return () => clearTimeout(timer);
    }
  }, [geoStatus]);

  const handleSend = async (text?: string) => {
    const content = text || input.trim();
    if (!content) return;
    if (isGuestLimitReached) return;
    if (!activeChatbotName) {
      toast({ title: "Erreur", description: "Aucun chatbot actif sélectionné", variant: "destructive" });
      return;
    }


    let convId = activeConversationId;
    if (!convId) {
      convId = await createConversation(user?.id); 
    }


    await addMessage(convId, "user", content, user?.id); 
    setInput("");

    if (isGuest) {
      setGuestMessageCount((c) => c + 1);
    }

    setIsTyping(true);
    if (!sessionId) {
      console.error("Session ID manquant !");
      return;
    }
    const currentSessionId = sessionId;

    try {
      const response = await sendMessage(
        content,
        activeChatbotName,
        currentSessionId,
        {
          onLocationRequesting: () => setGeoStatus("requesting"),
          onLocationGranted: () => setGeoStatus("granted"),
          onLocationDenied: () => setGeoStatus("denied"),
        }
      );

      if (response.needs_clarification && response.clarification_question) {

        await addMessage(convId, "assistant", response.clarification_question, user?.id);
      } else {
        await addMessage(convId, "assistant", response.answer, user?.id);
      }
    } catch (error) {
      console.error("Failed to get response:", error);
      toast({
        title: "Erreur",
        description: "Impossible d'obtenir une réponse. Veuillez réessayer.",
        variant: "destructive",
      });
      await addMessage(convId, "assistant", "Désolé, une erreur s'est produite. Veuillez réessayer.", user?.id);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex-1 flex flex-col h-screen bg-background">
      <header className="h-14 border-b border-border flex items-center justify-between px-5 shrink-0 bg-background/80 backdrop-blur">
        <div className="flex items-center gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-semibold text-foreground">
                {activeChatbot?.name || "Chatbot"}
              </h1>
              <span className="h-2 w-2 rounded-full bg-online" />
            </div>
            <p className="text-xs text-muted-foreground">
              {activeChatbot?.description || ""}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          {isGuest && (
            <>
              <Button onClick={() => navigate("/auth")} variant="outline" size="sm" className="gap-1.5 text-xs h-8">
                <LogIn size={14} />
                Se connecter
              </Button>
              <Button onClick={() => navigate("/auth")} size="sm" className="gap-1.5 text-xs h-8">
                <UserPlus size={14} />
                S'inscrire
              </Button>
            </>
          )}
          {activeConversationId && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-destructive"
              onClick={() => clearConversation(activeConversationId)}
            >
              <Trash2 size={16} />
            </Button>
          )}
        </div>
      </header>

      {messages.length === 0 && !isTyping ? (
        <WelcomeScreen onSuggestionClick={(text) => handleSend(text)} />
      ) : (
        <div className="flex-1 overflow-y-auto p-5 chat-scroll">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {isTyping && (
            <div className="flex gap-3 mb-4 animate-fade-in">
              <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                <Sparkles size={14} className="text-primary" />
              </div>
              <div className="bg-chat-assistant-bg px-4 py-3 rounded-2xl rounded-bl-md">
                <div className="flex gap-1">
                  <span className="h-2 w-2 rounded-full bg-muted-foreground animate-pulse-dot" />
                  <span className="h-2 w-2 rounded-full bg-muted-foreground animate-pulse-dot [animation-delay:0.3s]" />
                  <span className="h-2 w-2 rounded-full bg-muted-foreground animate-pulse-dot [animation-delay:0.6s]" />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      {geoStatus !== "idle" && (
        <div
          className={`px-4 py-2 flex items-center justify-center gap-2 text-xs font-medium transition-all duration-300 ${
            geoStatus === "requesting"
              ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
              : geoStatus === "granted"
              ? "bg-green-500/10 text-green-600 dark:text-green-400"
              : "bg-amber-500/10 text-amber-600 dark:text-amber-400"
          }`}
        >
          <MapPin size={13} className={geoStatus === "requesting" ? "animate-bounce" : ""} />
          {geoStatus === "requesting" && "Demande d'accès à votre position en cours..."}
          {geoStatus === "granted" && "✓ Position obtenue avec succès"}
          {geoStatus === "denied" && "Position non disponible — utilisation de la position par défaut"}
        </div>
      )}

      {isGuestLimitReached && (
        <div className="border-t border-border bg-muted/50 p-4 text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Lock size={16} className="text-primary" />
            <p className="text-sm font-medium text-foreground">Limite de messages atteinte</p>
          </div>
          <p className="text-xs text-muted-foreground mb-3">
            Créez un compte gratuit pour continuer à discuter et sauvegarder votre historique.
          </p>
          <Button size="sm" onClick={() => navigate("/auth")} className="gap-2">
            Créer un compte gratuitement
          </Button>
        </div>
      )}

      {!isGuestLimitReached && (
        <div className="border-t border-border p-4 shrink-0">
          <div className="flex gap-2 items-end max-w-3xl mx-auto">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Écrivez votre message..."
              rows={1}
              className="flex-1 resize-none rounded-xl border border-input bg-card px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 transition-shadow"
            />
            <Button
              onClick={() => handleSend()}
              disabled={!input.trim() || isTyping}
              size="icon"
              className="h-11 w-11 rounded-xl shrink-0"
            >
              <Send size={18} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatArea;