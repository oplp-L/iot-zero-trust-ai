import React from "react";

export default function StatCard({ title, value, color = "#1677ff" }) {
  return (
    <div style={{
      borderRadius: 10,
      padding: 16,
      background: "linear-gradient(135deg, #0b1220, #0f1a2b)",
      border: `1px solid ${color}`,
      color: "#e6f4ff",
      minWidth: 180
    }}>
      <div style={{ opacity: 0.75, fontSize: 12 }}>{title}</div>
      <div style={{ fontSize: 28, fontWeight: 700 }}>{value}</div>
    </div>
  );
}