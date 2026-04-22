import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import AfriquiaLogo from "@/components/AfriquiaLogo";
import { toast } from "@/hooks/use-toast";
import { LogIn, UserPlus, ArrowLeft } from "lucide-react";

const Auth = () => {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { signUp, signIn } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    if (isSignUp) {
      const { error } = await signUp(email, password);
      if (error) {
        toast({ title: "Erreur", description: error, variant: "destructive" });
      } else {
        toast({ title: "Compte créé ✅", description: `Bienvenue ${displayName} !` });
        navigate("/chat");
      }
    } else {
      const { error } = await signIn(email, password);
      if (error) {
        toast({ title: "Erreur", description: error, variant: "destructive" });
      } else {
        navigate("/chat");
      }
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-card border border-border rounded-2xl p-8 shadow-lg">
          <div className="flex flex-col items-center mb-8">
            <AfriquiaLogo size="lg" />
            <h1 className="text-xl font-bold text-foreground mt-4">
              {isSignUp ? "Créer un compte" : "Se connecter"}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              {isSignUp
                ? "Rejoignez Afriquia pour sauvegarder vos conversations"
                : "Accédez à votre historique de conversations"}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {isSignUp && (
              <div>
                <Label htmlFor="displayName">Nom d'affichage</Label>
                <Input
                  id="displayName"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Mohammed"
                  required
                />
              </div>
            )}
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="votre@email.com"
                required
              />
            </div>
            <div>
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={6}
              />
            </div>
            <Button type="submit" className="w-full gap-2" disabled={loading}>
              {isSignUp ? <UserPlus size={16} /> : <LogIn size={16} />}
              {loading ? "Chargement..." : isSignUp ? "S'inscrire" : "Se connecter"}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <button
              type="button"
              onClick={() => setIsSignUp(!isSignUp)}
              className="text-sm text-primary hover:underline"
            >
              {isSignUp ? "Déjà un compte ? Se connecter" : "Pas de compte ? S'inscrire"}
            </button>
          </div>

          <div className="mt-4 text-center">
            <button
              type="button"
              onClick={() => navigate("/chat")}
              className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1 mx-auto"
            >
              <ArrowLeft size={14} />
              Continuer en tant qu'invité
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Auth;