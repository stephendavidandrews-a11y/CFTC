import React from "react";
import { useNavigate } from "react-router-dom";
import EmptyState from "../components/shared/EmptyState";

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
      <EmptyState
        icon="404"
        title="Page Not Found"
        message="The page you're looking for doesn't exist or has been moved."
        actionLabel="Go to Dashboard"
        onAction={() => navigate("/")}
      />
    </div>
  );
}
