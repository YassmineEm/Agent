import { useState, createContext, useContext, ReactNode, useEffect } from "react";
import { getOrCreateSessionId } from "@/utils/session";
import { supabase } from "@/integrations/supabase/client";
import { User } from "@supabase/supabase-js";
import { useChatStore } from "@/stores/chatStore";

// 🔥 Type utilisateur (Supabase)
type UserInfo = User;

// 🔥 Type du context
interface AuthContextType {
  user: UserInfo | null;
  sessionId: string;
  loading: boolean;
  isGuest: boolean;
  profile: { display_name: string | null; avatar_url: string | null } | null;
  signUp: (email: string, password: string) => Promise<{ error?: string }>;
  signIn: (email: string, password: string) => Promise<{ error?: string }>;
  signOut: () => Promise<void>;
}

// 🔥 Valeur par défaut
const AuthContext = createContext<AuthContextType>({
  user: null,
  sessionId: "",
  loading: true,
  isGuest: true,
  profile: null,
  signUp: async () => ({}),
  signIn: async () => ({}),
  signOut: async () => {},
});

// 🔥 Provider principal
export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [sessionId, setSessionId] = useState<string>("");
  const [loading, setLoading] = useState(true);

  // 🔥 INIT AUTH (clé du système)
  useEffect(() => {
    const initAuth = async () => {
      const { data } = await supabase.auth.getUser();

      if (data.user) {
        // ✅ utilisateur connecté
        setUser(data.user);
        setSessionId(data.user.id);
      } else {
        // ✅ mode invité
        const guestSession = getOrCreateSessionId();
        setSessionId(guestSession);
      }

      setLoading(false);
    };

    initAuth();
  }, []);

  // 🔥 SIGN UP (Supabase)
  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
    });

    if (error) return { error: error.message };

    return {};
  };

  // 🔥 SIGN IN
  const signIn = async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) return { error: error.message };

    if (data.user) {
      setUser(data.user);
      setSessionId(data.user.id);
    }

    return {};
  };

  // 🔥 SIGN OUT → retour en invité
  const signOut = async () => {
    await supabase.auth.signOut();
    setUser(null);
    useChatStore.getState().resetStore();
    const guestSession = getOrCreateSessionId();
    setSessionId(guestSession);
  };

  // 🔥 PROFILE
  const profile = user
    ? {
        display_name: user.user_metadata?.display_name ?? null,
        avatar_url: user.user_metadata?.avatar_url ?? null,
      }
    : null;

  return (
    <AuthContext.Provider
      value={{
        user,
        sessionId,
        loading,
        isGuest: !user,
        profile,
        signUp,
        signIn,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

// 🔥 Hook custom
export const useAuth = () => useContext(AuthContext);