import ChatSidebar from "@/components/chat/ChatSidebar";
import ChatArea from "@/components/chat/ChatArea";
import { useAuth } from "@/hooks/useAuth";

const Chat = () => {
  const { isGuest } = useAuth();

  return (
    <div className="flex h-screen w-full overflow-hidden">
      {!isGuest && <ChatSidebar />}
      <ChatArea />
    </div>
  );
};

export default Chat;
