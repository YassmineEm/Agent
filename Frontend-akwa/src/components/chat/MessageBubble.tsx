import { format } from "date-fns";
import { Flame } from "lucide-react";
import type { Message } from "@/stores/chatStore";

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble = ({ message }: MessageBubbleProps) => {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex gap-3 mb-4 animate-fade-in ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
    >
      {/* Avatar */}
      {isUser ? (
        <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-semibold shrink-0">
          MA
        </div>
      ) : (
        <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
          <Flame size={16} className="text-primary" />
        </div>
      )}

      {/* Bubble */}
      <div className={`max-w-[70%] ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? "bg-chat-user-bg text-chat-user-fg rounded-br-md"
              : "bg-chat-assistant-bg text-chat-assistant-fg rounded-bl-md"
          }`}
        >
          {message.content}
        </div>
        <p
          className={`text-[10px] text-muted-foreground mt-1 px-1 ${
            isUser ? "text-right" : "text-left"
          }`}
        >
          {format(message.timestamp, "HH:mm")}
        </p>
      </div>
    </div>
  );
};

export default MessageBubble;
