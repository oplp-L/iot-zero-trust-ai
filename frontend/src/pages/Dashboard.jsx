import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import StatCard from "../components/StatCard";

export default function Dashboard() {
  const [routesCount, setRoutesCount] = useState(0);
  const [build, setBuild] = useState("-");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const run = async () => {
      try {
        const r = await api.get("/__routes");
        setRoutesCount(r.data.count);
        setBuild(r.data.build);
      } catch (e) {
        setError(e.message || "Failed to reach backend");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

  return (
    <div style={{ padding: 24, color: "#e6f4ff", background: "#0a0f1a", minHeight: "100vh" }}>
      <h2 style={{ marginBottom: 16 }}>IoT Zero Trust AI 控制台</h2>
      {loading ? <div>Loading…</div> : error ? <div style={{ color: "#ff4d4f" }}>{error}</div> : (
        <>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <StatCard title="后端可用路由" value={routesCount} />
            <StatCard title="后端构建标签" value={build} color="#52c41a" />
          </div>
          <div style={{ marginTop: 24, opacity: 0.8 }}>
            <p>下一步：加入设备列表、事件时间轴、风险面板与处置审计。</p>
          </div>
        </>
      )}
    </div>
  );
}