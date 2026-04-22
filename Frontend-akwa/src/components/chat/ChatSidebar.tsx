// src/components/chat/ChatSidebar.tsx
import { Plus, MessageSquare, LogIn, LogOut } from "lucide-react"; // ← MessageSquare ajouté
import { useNavigate } from "react-router-dom";
import AfriquiaLogo from "@/components/AfriquiaLogo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useChatStore } from "@/stores/chatStore";
import { useAuth } from "@/hooks/useAuth";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

const ChatSidebar = () => {
  const navigate = useNavigate();
  const { user, isGuest, profile, signOut } = useAuth();
  const {
    chatbots,
    activeChatbotName,
    setActiveChatbot,
    conversations,
    activeConversationId,
    setActiveConversation,
    createConversation,
  } = useChatStore();

  const activeChatbot = chatbots.find((b) => b.name === activeChatbotName);
  const recentConversations = conversations
    .filter((c) => c.chatbotName === activeChatbotName) // ← utiliser chatbotName
    .slice(0, 5);

  const initials = profile?.display_name
    ? profile.display_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "?";

  return (
    <aside className="w-[280px] h-screen flex flex-col border-r border-border bg-card">
      <div className="p-5 pb-3 flex items-center justify-between">
        <div>
          <AfriquiaLogo size="md" />
          <p className="text-xs text-muted-foreground mt-1">Assistant Afriquia</p>
        </div>
        <ThemeToggle />
      </div>

      <Separator />

      <div className="p-4">
        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2 block">
          Chatbot actif
        </label>
        <Select
          value={activeChatbotName || undefined}
          onValueChange={(v) => {
            setActiveChatbot(v);
            setActiveConversation(null);
          }}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Sélectionner un chatbot" />
          </SelectTrigger>
          <SelectContent>
            {chatbots.map((bot) => (
              <SelectItem key={bot.name} value={bot.name}>
                {bot.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-1.5 mt-2">
          <span className="h-2 w-2 rounded-full bg-online animate-pulse-dot" />
          <span className="text-xs text-muted-foreground">En ligne</span>
        </div>
      </div>

      <Separator />

      <div className="px-4 pt-4 pb-2">
        <Button
          onClick={() => createConversation()}
          className="w-full gap-2"
          size="sm"
          disabled={!activeChatbotName}
        >
          <Plus size={16} />
          Nouvelle conversation
        </Button>
      </div>

      <div className="px-4 pb-2">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Conversations récentes
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-2 chat-scroll">
        {isGuest ? (
          <div className="p-3 text-center">
            <p className="text-xs text-muted-foreground mb-2">
              Connectez-vous pour sauvegarder votre historique
            </p>
          </div>
        ) : recentConversations.length === 0 ? (
          <p className="text-xs text-muted-foreground p-3 text-center">
            Aucune conversation
          </p>
        ) : (
          recentConversations.map((conv) => (
            <button
              key={conv.id}
              onClick={() => setActiveConversation(conv.id)}
              className={`w-full text-left p-3 rounded-lg mb-1 transition-colors hover:bg-accent group ${
                activeConversationId === conv.id ? "bg-accent" : ""
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <MessageSquare size={14} className="text-muted-foreground shrink-0" />
                <span className="text-sm font-medium truncate text-foreground">
                  {conv.title}
                </span>
              </div>
              <p className="text-xs text-muted-foreground truncate pl-[22px]">
                {conv.preview || "Pas encore de messages"}
              </p>
              <p className="text-[10px] text-muted-foreground mt-1 pl-[22px]">
                {formatDistanceToNow(conv.updatedAt, { addSuffix: true, locale: fr })}
              </p>
            </button>
          ))
        )}
      </div>

      <Separator />

      <div className="p-4">
        {isGuest ? (
          <div className="flex flex-col gap-2">
            <Button onClick={() => navigate("/auth")} className="w-full gap-2" size="sm">
              <LogIn size={16} />
              Se connecter
            </Button>
            <Button onClick={() => navigate("/auth")} variant="outline" className="w-full gap-2" size="sm">
              S'inscrire
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-sm font-semibold shrink-0">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">
                {profile?.display_name || user?.email}
              </p>
              <p className="text-xs text-muted-foreground">Connecté</p>
            </div>
            <button
              onClick={signOut}
              className="text-muted-foreground hover:text-destructive transition-colors"
              title="Se déconnecter"
            >
              <LogOut size={18} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
};

export default ChatSidebar;