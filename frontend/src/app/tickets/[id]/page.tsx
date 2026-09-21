"use client";

import { useParams } from "next/navigation";
import { ConsoleView } from "@/components/console/console-view";

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  return <ConsoleView selectedTicketId={id} />;
}
