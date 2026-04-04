"use client";

import { useEffect, useState } from "react";

export default function BackendStatus() {
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    fetch("/api/v1/health")
      .then(() => setStatus("ok"))
      .catch(() => setStatus("fail"));
  }, []);

  if (status === "ok") return null;

  return (
    <div style={{position:"fixed",bottom:16,left:16,background:"red",color:"white",padding:"8px 12px",borderRadius:8}}>
      Backend disconnected
    </div>
  );
}
