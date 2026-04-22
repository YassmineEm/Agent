// src/stores/chatStore.ts

import { create } from "zustand";
import { fetchChatbots } from "@/services/api";
import { supabase } from "@/integrations/supabase/client";

export const GUEST_CHATBOT_NAME = "Afriquia";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export interface Conversation {
  id: string;
  chatbotName: string;
  chatbotId: string;
  title: string;
  preview: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

export interface Chatbot {
  id: number;
  name: string;
  description: string;
  active: boolean;
}

interface ChatState {
  chatbots: Chatbot[];
  activeChatbotName: string | null;
  conversations: Conversation[];
  activeConversationId: string | null;

  loadChatbots: (isGuest?: boolean, userId?: string) => Promise<void>;
  loadConversations: (userId: string) => Promise<void>;
  setActiveChatbot: (name: string) => void;
  setActiveConversation: (id: string | null) => void;
  createConversation: (userId?: string) => Promise<string>;
  addMessage: (conversationId: string, role: "user" | "assistant", content: string, userId?: string) => Promise<void>;
  clearConversation: (conversationId: string) => void;
  resetStore: () => void;
}

const generateId = () => Math.random().toString(36).substring(2, 10);

export const useChatStore = create<ChatState>((set, get) => ({
  chatbots: [],
  activeChatbotName: null,
  conversations: [],
  activeConversationId: null,

  loadChatbots: async (isGuest = true, userId?: string) => {
    try {
      const data = await fetchChatbots(isGuest ? undefined : userId);
      const activeChatbots = data.chatbots.filter((b: Chatbot) => b.active);
      set({ chatbots: activeChatbots });

      if (activeChatbots.length > 0 && !get().activeChatbotName) {
        if (isGuest) {
          const afriquia = activeChatbots.find((b: Chatbot) => b.name === GUEST_CHATBOT_NAME);
          set({ activeChatbotName: afriquia?.name ?? activeChatbots[0].name });
        } else {
          set({ activeChatbotName: activeChatbots[0].name });
        }
      }
    } catch (error) {
      console.error("Erreur chargement chatbots :", error);
    }
  },

  // ✅ Avec preview maintenant disponible
  loadConversations: async (userId: string) => {
    const { data: convs, error } = await supabase
      .from("conversations")
      .select(`
        id, 
        chatbot_id, 
        title, 
        preview,
        created_at, 
        updated_at,
        messages (
          id, 
          role, 
          content, 
          created_at
        )
      `)
      .eq("user_id", userId)
      .order("updated_at", { ascending: false });

    if (error) { 
      console.error("Erreur chargement conversations :", error); 
      return; 
    }

    const chatbots = get().chatbots;

    const conversations: Conversation[] = (convs || []).map((c) => ({
      id: c.id,
      chatbotId: c.chatbot_id,
      chatbotName: chatbots.find((b) => String(b.id) === c.chatbot_id)?.name ?? c.chatbot_id,
      title: c.title ?? "Nouvelle conversation",
      preview: c.preview ?? "",
      createdAt: new Date(c.created_at ?? new Date()),
      updatedAt: new Date(c.updated_at ?? new Date()),
      messages: (c.messages || []).map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant",
        content: m.content ?? "",
        timestamp: new Date(m.created_at ?? new Date()),
      })),
    }));

    set({ conversations });
  },

  setActiveChatbot: (name) => set({ activeChatbotName: name }),
  
  setActiveConversation: (id) => set({ activeConversationId: id }),

  createConversation: async (userId?: string) => {
    const activeName = get().activeChatbotName;
    const activeChatbot = get().chatbots.find((b) => b.name === activeName);

    if (userId && activeChatbot) {
      const { data, error } = await supabase
        .from("conversations")
        .insert({
          user_id: userId,
          chatbot_id: String(activeChatbot.id),
          title: "Nouvelle conversation",
          preview: "",
        })
        .select()
        .single();

      if (!error && data) {
        const newConv: Conversation = {
          id: data.id,
          chatbotId: String(activeChatbot.id),
          chatbotName: activeName!,
          title: data.title ?? "Nouvelle conversation",
          preview: data.preview ?? "",
          messages: [],
          createdAt: new Date(data.created_at ?? new Date()),
          updatedAt: new Date(data.updated_at ?? new Date()),
        };
        set((state) => ({
          conversations: [newConv, ...state.conversations],
          activeConversationId: data.id,
        }));
        return data.id;
      }
    }

    // Fallback local (invité)
    const id = `local_${generateId()}`;
    const newConv: Conversation = {
      id,
      chatbotId: String(activeChatbot?.id ?? ""),
      chatbotName: activeName ?? "",
      title: "Nouvelle conversation",
      preview: "",
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    set((state) => ({
      conversations: [newConv, ...state.conversations],
      activeConversationId: id,
    }));
    return id;
  },

  addMessage: async (conversationId, role, content, userId?) => {
    const newMsg: Message = {
      id: generateId(),
      role,
      content,
      timestamp: new Date(),
    };

    // Mise à jour locale immédiate
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId
          ? {
              ...conv,
              messages: [...conv.messages, newMsg],
              preview: content.slice(0, 60),
              title: conv.messages.length === 0 && role === "user"
                ? content.slice(0, 40)
                : conv.title,
              updatedAt: new Date(),
            }
          : conv
      ),
    }));

    // Persistance Supabase si connecté ET conversation non locale
    if (userId && !conversationId.startsWith("local_")) {
      await supabase.from("messages").insert({
        conversation_id: conversationId,
        role,
        content,
      });

      // Mettre à jour la conversation
      const conv = get().conversations.find((c) => c.id === conversationId);
      if (conv) {
        await supabase
          .from("conversations")
          .update({ 
            preview: content.slice(0, 60),
            title: conv.title,
            updated_at: new Date().toISOString()
          })
          .eq("id", conversationId);
      }
    }
  },

  clearConversation: (conversationId) => {
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId
          ? { ...conv, messages: [], preview: "", updatedAt: new Date() }
          : conv
      ),
    }));
  },

  resetStore: () => {
    set({
      conversations: [],
      activeConversationId: null,
    });
  },
}));