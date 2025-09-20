import React, { useState } from "react";
import { Form, Input, Button, message, Card } from "antd";
import axios from "axios";
import { useNavigate } from "react-router-dom";

const api = "http://127.0.0.1:8000";

export default function LoginPage({ onLoginSuccess }) {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values) => {
    setLoading(true);
    try {
      // OAuth2 密码模式需要 x-www-form-urlencoded
      const form = new URLSearchParams();
      form.append("username", values.username);
      form.append("password", values.password);

      const res = await axios.post(`${api}/users/token`, form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      const token = res.data?.access_token;
      if (!token) {
        message.error("登录失败：未收到 token");
        return;
      }

      // 本地保存 token，并全局注入 axios
      localStorage.setItem("token", token);
      axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;

      // 通知 App.js 更新状态（可选）
      if (typeof onLoginSuccess === "function") onLoginSuccess(token);

      message.success("登录成功");
      navigate("/", { replace: true }); // 跳到首页（受保护路由）
    } catch (e) {
      if (e.response?.status === 401) {
        message.error("用户名或密码错误");
      } else {
        message.error("登录失败，请稍后再试");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
      <Card title="登录" style={{ width: 380 }}>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item
            label="用户名"
            name="username"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input placeholder="alice" />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password placeholder="********" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}