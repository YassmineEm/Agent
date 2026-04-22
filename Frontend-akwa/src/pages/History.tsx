// src/pages/History.tsx
import { useState } from "react";
import { Search, Calendar, Filter, MessageSquare, ArrowLeft } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useChatStore } from "@/stores/chatStore";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { useNavigate } from "react-router-dom";
import AfriquiaLogo from "@/components/AfriquiaLogo";

const History = () => {
  const { conversations, setActiveConversation, setActiveChatbot, chatbots } = useChatStore();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [botFilter, setBotFilter] = useState<string>("all");
  const [dateFilter, setDateFilter] = useState<string>("all");

  const filtered = conversations.filter((c) => {
    if (botFilter !== "all" && c.chatbotName !== botFilter) return false;
    if (search && !c.title.toLowerCase().includes(search.toLowerCase()) && !c.preview.toLowerCase().includes(search.toLowerCase())) return false;
    if (dateFilter === "today") {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (c.updatedAt < today) return false;
    } else if (dateFilter === "week") {
      const week = new Date(Date.now() - 7 * 86400000);
      if (c.updatedAt < week) return false;
    } else if (dateFilter === "month") {
      const month = new Date(Date.now() - 30 * 86400000);
      if (c.updatedAt < month) return false;
    }
    return true;
  });

  const openConversation = (conv: typeof conversations[0]) => {
    // On utilise le nom du chatbot pour le sélectionner
    setActiveChatbot(conv.chatbotName);
    setActiveConversation(conv.id);
    navigate("/chat");
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate("/chat")}>
              <ArrowLeft size={18} />
            </Button>
            <div>
              <h1 className="text-lg font-semibold text-foreground">Historique des conversations</h1>
              <p className="text-sm text-muted-foreground">{conversations.length} conversations au total</p>
            </div>
          </div>
          <AfriquiaLogo size="sm" />
        </div>
      </header>

      {/* Filters */}
      <div className="max-w-5xl mx-auto px-6 py-4">
        <div className="flex flex-wrap gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Rechercher dans les conversations..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={dateFilter} onValueChange={setDateFilter}>
            <SelectTrigger className="w-[160px]">
              <Calendar size={14} className="mr-2" />
              <SelectValue placeholder="Période" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toute période</SelectItem>
              <SelectItem value="today">Aujourd'hui</SelectItem>
              <SelectItem value="week">Cette semaine</SelectItem>
              <SelectItem value="month">Ce mois</SelectItem>
            </SelectContent>
          </Select>
          <Select value={botFilter} onValueChange={setBotFilter}>
            <SelectTrigger className="w-[160px]">
              <Filter size={14} className="mr-2" />
              <SelectValue placeholder="Chatbot" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les chatbots</SelectItem>
              {chatbots.map((bot) => (
                <SelectItem key={bot.name} value={bot.name}>{bot.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* List */}
      <div className="max-w-5xl mx-auto px-6 pb-8">
        {filtered.length === 0 ? (
          <div className="text-center py-16">
            <MessageSquare size={40} className="mx-auto text-muted-foreground mb-3" />
            <p className="text-muted-foreground">Aucune conversation trouvée</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((conv) => {
              const bot = chatbots.find((b) => b.name === conv.chatbotName);
              return (
                <button
                  key={conv.id}
                  onClick={() => openConversation(conv)}
                  className="w-full text-left p-4 rounded-xl border border-border bg-card hover:bg-accent transition-colors animate-fade-in"
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <MessageSquare size={16} className="text-primary" />
                      <span className="font-medium text-sm text-foreground">{conv.title}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
                        {bot?.name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {format(conv.updatedAt, "dd MMM yyyy · HH:mm", { locale: fr })}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground pl-[24px]">
                    {conv.preview || "Conversation vide"}
                  </p>
                  <p className="text-xs text-muted-foreground pl-[24px] mt-1">
                    {conv.messages.length} message{conv.messages.length !== 1 ? "s" : ""}
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default History;