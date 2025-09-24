import React, { useEffect, useState } from "react";
import { Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import DevicePage from "./pages/DevicePage";
import UserPage from "./pages/UserPage";
import GroupPage from "./pages/GroupPage";
import LoginPage from "./pages/LoginPage";
import Dashboard from "./pages/Dashboard";
import { Layout, Menu, Button, Avatar, Dropdown, message } from "antd";
import { UserOutlined, DashboardOutlined, AppstoreOutlined, TeamOutlined, LogoutOutlined } from "@ant-design/icons";

const { Header, Content } = Layout;

function RequireAuth({ children }) {
  const token = localStorage.getItem("token");
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));
  const [showLoginModal, setShowLoginModal] = useState(false); // 控制登录弹窗
  const username = "Admin";
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common["Authorization"];
    }

    const resInterceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response && error.response.status === 401) {
          localStorage.removeItem("token");
          delete axios.defaults.headers.common["Authorization"];
          window.location.href = "/login";
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.response.eject(resInterceptor);
    };
  }, [token]);

  const handleLogout = () => {
    localStorage.removeItem("token");
    delete axios.defaults.headers.common["Authorization"];
    setToken(null);
    message.success("已退出登录");
    window.location.href = "/login";
  };

  const handleLoginSuccess = (newToken) => {
    setToken(newToken);
    axios.defaults.headers.common["Authorization"] = `Bearer ${newToken}`;
    setShowLoginModal(false); // 登录成功关闭弹窗
  };

  // 使用 useLocation 获取当前路由，实现菜单高亮
  const path = location.pathname;
  const menuKeyMap = {
    "/dashboard": "dashboard",
    "/": "devices",
    "/users": "users",
    "/groups": "groups"
  };
  const selectedKey = menuKeyMap[path] || "dashboard";

  // 右上角用户下拉菜单
  const userDropdown = (
    <Dropdown
      menu={{
        items: [
          {
            key: "logout",
            label: (
              <span onClick={handleLogout}>
                <LogoutOutlined /> 退出登录
              </span>
            ),
          },
        ]
      }}
      placement="bottomRight"
      arrow
    >
      <span style={{ cursor: "pointer", display: "flex", alignItems: "center" }}>
        <Avatar icon={<UserOutlined />} style={{ marginRight: 8 }} />
        <span style={{ color: "#fff", marginRight: 8 }}>{username}</span>
      </span>
    </Dropdown>
  );

  // 菜单点击控制：未登录弹窗提示，已登录正常跳转
  const handleMenuClick = ({ key }) => {
    if (!token && key !== "login") {
      setShowLoginModal(true); // 每次点击都弹窗
      navigate("/login");
      return;
    }
    switch (key) {
      case "dashboard":
        navigate("/dashboard");
        break;
      case "devices":
        navigate("/");
        break;
      case "users":
        navigate("/users");
        break;
      case "groups":
        navigate("/groups");
        break;
      default:
        break;
    }
  };

  return (
    <Layout style={{ minHeight: "100vh", background: "#f4f8fb" }}>
      {/* 顶部导航栏 */}
      <Header style={{
        display: "flex",
        alignItems: "center",
        background: "#001529",
        boxShadow: "0 2px 8px #00000026",
        zIndex: 10
      }}>
        {/* LOGO与系统名 */}
        <div style={{ color: "#fff", fontSize: 22, fontWeight: "bold", marginRight: 32, letterSpacing: 2 }}>
          <DashboardOutlined style={{ fontSize: 28, marginRight: 10 }} />
          IoT Zero Trust AI
        </div>

        {/* 菜单 */}
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selectedKey]}
          style={{ flex: 1, background: "transparent" }}
          onClick={handleMenuClick}
        >
          <Menu.Item key="dashboard" icon={<DashboardOutlined />}>
            仪表盘
          </Menu.Item>
          <Menu.Item key="devices" icon={<AppstoreOutlined />}>
            设备管理
          </Menu.Item>
          <Menu.Item key="users" icon={<UserOutlined />}>
            用户管理
          </Menu.Item>
          <Menu.Item key="groups" icon={<TeamOutlined />}>
            分组管理
          </Menu.Item>
        </Menu>

        {/* 右侧用户区 */}
        <div style={{ marginLeft: 16 }}>
          {token ? userDropdown : (
            <Button onClick={() => navigate("/login")}>登录</Button>
          )}
        </div>
      </Header>

      {/* 主内容区 */}
      <Content style={{
        padding: "32px 24px",
        maxWidth: 1300,
        margin: "0 auto",
        width: "100%",
        minHeight: "calc(100vh - 64px)",
      }}>
        <Routes>
          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          />
          <Route
            path="/"
            element={
              <RequireAuth>
                <DevicePage />
              </RequireAuth>
            }
          />
          <Route
            path="/users"
            element={
              <RequireAuth>
                <UserPage />
              </RequireAuth>
            }
          />
          <Route
            path="/groups"
            element={
              <RequireAuth>
                <GroupPage />
              </RequireAuth>
            }
          />
          <Route
            path="/login"
            element={
              <LoginPage
                onLoginSuccess={handleLoginSuccess}
                showLoginModal={showLoginModal}
                setShowLoginModal={setShowLoginModal}
              />
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Content>
    </Layout>
  );
}

export default App;