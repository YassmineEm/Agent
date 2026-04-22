// src/services/api.ts

import { supabase } from "@/integrations/supabase/client";
import type { Database } from "@/integrations/supabase/types";

// Type pour les chatbots retournés par Django
interface DjangoChatbot {
  id: number;
  name: string;
  description: string;
  active: boolean;
}

export interface OrchestratorResponse {
  answer: string;
  needs_clarification?: boolean;
  clarification_question?: string;
  agents_used?: string[];
  confidence?: number;
  routing_method?: string;
  trace_id?: string;
  session_id?: string;
}

interface SendMessagePayload {
  session_id: string;
  question: string;
  chatbot_id: string;
  lat?: number;
  lng?: number;
}

interface GeoCallbacks {
  onLocationRequesting?: () => void;
  onLocationGranted?: () => void;
  onLocationDenied?: () => void;
}

const ADMIN_API_BASE_URL = import.meta.env.VITE_ADMIN_API_URL || "http://localhost:8000";
const CHAT_API_BASE_URL = import.meta.env.VITE_ORCHESTRATOR_API_URL || "http://localhost:8001";

function getBrowserLocation(): Promise<{ lat: number; lng: number }> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Géolocalisation non supportée par ce navigateur"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({
        lat: position.coords.latitude,
        lng: position.coords.longitude,
      }),
      (error) => reject(error),
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
    );
  });
}

function isLocationQuestion(question: string): boolean {
  const keywords = [
    "proche de moi", "près de moi", "la plus proche", "le plus proche",
    "les plus proches", "station proche", "à proximité", "autour de moi",
    "proche de ma position", "station la plus proche", "point de vente proche",
    "pas loin de moi", "dans mon quartier", "dans ma ville", "dans ma région",
    "où se trouve", "où est", "localisation", "ma position", "ma localisation",
    "coordonnées", "géolocalisation", "adresse", "itinéraire", "comment aller",
    "comment accéder", "trouver une station", "trouver le distributeur",
    "distance", "combien de kilomètres", "combien de km", "à quelle distance",
    "temps de trajet",
    "near me", "near my location", "nearest station", "closest station",
    "my location", "around me", "nearby", "directions to", "how far",
    "closest", "find a station",
    "قريب مني", "قريبة مني", "الأقرب", "الأقرب إلي", "أقرب محطة",
    "أقرب نقطة بيع", "أقرب موقع", "المحطة الأقرب", "النقطة الأقرب",
    "كم تبعد", "المسافة", "كم كيلومتر", "كم كلم", "بعد كم", "المسافة إلى",
    "أين توجد", "أين تقع", "موقع", "مكان", "عنوان", "الاتجاهات",
    "كيف أصل إلى", "طريق", "حدد موقعي", "إحداثيات", "خرائط",
    "أقرب محطة عني",
  ];
  const q = question.toLowerCase();
  return keywords.some(keyword => q.includes(keyword));
}

function getOrCreateSessionId(chatbotId: string): string {
  const storageKey = `afriquia_session_${chatbotId}`;
  let sessionId = localStorage.getItem(storageKey);
  if (!sessionId) {
    sessionId = `guest_${Date.now()}`;
    localStorage.setItem(storageKey, sessionId);
  }
  return sessionId;
}

// Version type-safe sans any
export const fetchChatbots = async (userId?: string): Promise<{ chatbots: DjangoChatbot[] }> => {
  // 1. Charger tous les chatbots actifs depuis Django
  const res = await fetch(`${ADMIN_API_BASE_URL}/api/chatbots/`);
  if (!res.ok) throw new Error("Impossible de récupérer la liste des chatbots");
  const data = await res.json();
  const allChatbots: DjangoChatbot[] = data.chatbots;

  // 2. Si invité → retourner seulement "Afriquia" (chatbot public)
  if (!userId) {
    return { chatbots: allChatbots.filter((b) => b.name === "Afriquia") };
  }

  // 3. Si connecté → filtrer par accès Supabase (typesafe !)
  const { data: access, error } = await supabase
    .from("user_chatbot_access")
    .select("chatbot_id")
    .eq("user_id", userId);

  if (error || !access) {
    console.error("Erreur accès chatbots :", error);
    return { chatbots: [] };
  }

  const allowedIds = new Set(access.map((a) => a.chatbot_id));

  const filtered = allChatbots.filter(
    (b) => allowedIds.has(String(b.id)) || b.name === "Afriquia"
  );

  return { chatbots: filtered };
};

export const sendMessage = async (
  question: string,
  chatbotId: string,
  sessionId?: string,
  geoCallbacks?: GeoCallbacks
): Promise<OrchestratorResponse> => {

  const resolvedSessionId = sessionId ?? getOrCreateSessionId(chatbotId);

  const payload: SendMessagePayload = {
    session_id: resolvedSessionId,
    question,
    chatbot_id: chatbotId,
  };

  if (isLocationQuestion(question)) {
    geoCallbacks?.onLocationRequesting?.();
    try {
      const { lat, lng } = await getBrowserLocation();
      payload.lat = lat;
      payload.lng = lng;
      geoCallbacks?.onLocationGranted?.();
      console.log("📍 Position réelle obtenue :", lat, lng);
    } catch (err) {
      payload.lat = 33.5731;
      payload.lng = -7.5898;
      geoCallbacks?.onLocationDenied?.();
      console.warn("⚠️ Géolocalisation échouée → fallback Casablanca :", err);
    }
  }

  console.log("📤 Envoi à l'orchestrateur :", payload);

  try {
    const response = await fetch(`${CHAT_API_BASE_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error("❌ Erreur API :", errorText);
      throw new Error(`Erreur HTTP ${response.status}`);
    }

    const data: OrchestratorResponse = await response.json();
    console.log("📥 Réponse orchestrateur :", data);

    if (data.session_id) {
      localStorage.setItem(`afriquia_session_${chatbotId}`, data.session_id);
    }

    return data;
  } catch (error) {
    console.error("🚨 Erreur réseau :", error);
    throw error;
  }
};