import AfriquiaLogo from "@/components/AfriquiaLogo";
import { Fuel, MapPin, Package, FileText } from "lucide-react";

interface WelcomeScreenProps {
  onSuggestionClick: (text: string) => void;
}

const suggestions = [
  { icon: Fuel, text: "Prix du gazoil aujourd'hui ?" },
  { icon: MapPin, text: "Localiser une station Afriquia près de moi" },
  { icon: Package, text: "État de mes commandes en cours" },
  { icon: FileText, text: "Documentation technique carburant" },
];

const WelcomeScreen = ({ onSuggestionClick }: WelcomeScreenProps) => {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 animate-fade-in">
      <div className="mb-6">
        <AfriquiaLogo size="lg" />
      </div>
      <h2 className="text-2xl font-semibold text-foreground mb-2">
        Bonjour, comment puis-je vous aider ?
      </h2>
      <p className="text-muted-foreground mb-8 text-center max-w-md">
        Je suis votre assistant Afriquia. Posez-moi vos questions sur les carburants, le gaz, les stations ou vos commandes.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
        {suggestions.map((s) => (
          <button
            key={s.text}
            onClick={() => onSuggestionClick(s.text)}
            className="flex items-center gap-3 p-4 rounded-xl border border-border bg-card hover:bg-accent hover:border-primary/20 transition-all text-left group"
          >
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 group-hover:bg-primary/15 transition-colors">
              <s.icon size={20} className="text-primary" />
            </div>
            <span className="text-sm text-foreground leading-snug">{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default WelcomeScreen;
