import React, { useState } from "react";
import { Form, Input, Button, message, Card, Typography, Modal } from "antd";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import logo from "../assets/logo.png";
import bgImg from "../assets/ai-bg.png";

const { Title, Text } = Typography;

const api = "http://127.0.0.1:8000";

export default function LoginPage({ onLoginSuccess, showLoginModal, setShowLoginModal }) {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // 登录表单提交成功
  const onFinish = async (values) => {
    setLoading(true);
    try {
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

      localStorage.setItem("token", token);
      axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
      if (typeof onLoginSuccess === "function") onLoginSuccess(token);

      message.success("登录成功");
      navigate("/", { replace: true });
    } catch (e) {
      if (e.response?.status === 401) {
        message.error("用户名或密码输入错误，请重新输入！");
      } else {
        message.error("登录失败，请稍后再试");
      }
    } finally {
      setLoading(false);
    }
  };

  // 表单校验失败（如未填写用户名或密码）
  const onFinishFailed = ({ errorFields }) => {
    if (errorFields && errorFields.length > 0) {
      message.error(errorFields[0].errors[0]);
    }
  };

  return (
    <div
      style={{
        minHeight: "calc(100vh - 64px)",
        width: "100vw",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(120deg, #e7f0fd 45%, #e5eaff 100%)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 色斑/光斑装饰 */}
      <div style={{
        position: "absolute",
        left: -180,
        top: -120,
        width: 380,
        height: 380,
        background: "radial-gradient(circle at 60% 40%, #6ab7ff88 0%, #fff0 80%)",
        filter: "blur(32px)",
        zIndex: 0,
      }} />
      <div style={{
        position: "absolute",
        right: 10,
        bottom: 60,
        width: 200,
        height: 200,
        background: "radial-gradient(circle at 50% 70%, #c984ff99 0%, #fff0 80%)",
        filter: "blur(32px)",
        zIndex: 0,
      }} />

      <div style={{ display: "flex", flexDirection: "row", alignItems: "center", zIndex: 1 }}>
        {/* 登录表单 */}
        <Card
          style={{
            width: 400,
            marginRight: 64,
            padding: "36px 28px 28px 28px",
            background: "rgba(255,255,255,0.98)",
            boxShadow: "0 10px 36px #7c9aff33, 0 1.5px 16px #ab93ff22",
            borderRadius: 22,
            border: "1px solid #e3e4fa",
            backdropFilter: "blur(3px)",
          }}
          bordered={false}
        >
          <div style={{ textAlign: "center", marginBottom: 18 }}>
            <img src={logo} alt="logo" style={{ height: 52, marginBottom: 8, filter: "drop-shadow(0 0 8px #b4d5ff55)" }} />
            <Title level={3} style={{ marginBottom: 0, fontWeight: 700, letterSpacing: 1 }}>
              IoT Zero Trust AI 平台
            </Title>
            <Text type="secondary" style={{ fontSize: 15 }}>
              物联网零信任 · 智能安全管理系统
            </Text>
          </div>
          <Form
            layout="vertical"
            onFinish={onFinish}
            onFinishFailed={onFinishFailed}
          >
            <Form.Item
              label="用户名"
              name="username"
              rules={[{ required: true, message: "请输入用户名！" }]}
            >
              <Input placeholder="请输入用户名" />
            </Form.Item>
            <Form.Item
              label="密码"
              name="password"
              rules={[{ required: true, message: "请输入密码！" }]}
            >
              <Input.Password placeholder="请输入密码" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit" loading={loading} block style={{
                fontWeight: 600,
                fontSize: 16,
                background: "linear-gradient(90deg,#6ab7ff 0%,#a984ff 100%)",
                border: "none"
              }}>
                登录
              </Button>
            </Form.Item>
          </Form>
        </Card>
        {/* 插画图片 */}
        <div style={{
          position: "relative",
          marginLeft: 24,
          width: 340,
          height: 288,
          display: "flex",
          alignItems: "center",
          justifyContent: "center"
        }}>
          {/* 插画底部光圈 */}
          <div style={{
            position: "absolute",
            left: 60,
            top: 140,
            width: 180,
            height: 80,
            background: "radial-gradient(circle,#c7dfff66 0%,#fff0 70%)",
            filter: "blur(18px)",
            zIndex: 0
          }} />
          <img
            src={bgImg}
            alt="ai-bg"
            style={{
              width: 270,
              opacity: 0.93,
              pointerEvents: "none",
              zIndex: 1,
              borderRadius: 12,
              boxShadow: "0 4px 32px #b3cdff33"
            }}
          />
        </div>
      </div>
      {/* 登录弹窗 */}
      <Modal
        open={!!showLoginModal}
        onOk={() => setShowLoginModal && setShowLoginModal(false)}
        onCancel={() => setShowLoginModal && setShowLoginModal(false)}
        okText="知道了"
        cancelButtonProps={{ style: { display: "none" } }}
        centered
        maskClosable={false}
      >
        <Title level={4}>请先登录</Title>
        <p>您需要登录后才能访问和使用本平台的所有功能。</p>
      </Modal>
    </div>
  );
}