import afriquiaLogo from "@/assets/afriquia-logo.png";

interface AfriquiaLogoProps {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
}

const sizeMap = {
  sm: "h-8",
  md: "h-10",
  lg: "h-16",
};

const AfriquiaLogo = ({ size = "md", showText = true }: AfriquiaLogoProps) => {
  return (
    <div className="flex items-center gap-2">
      <img
        src={afriquiaLogo}
        alt="Afriquia"
        className={`${sizeMap[size]} w-auto object-contain`}
      />
    </div>
  );
};

export default AfriquiaLogo;
