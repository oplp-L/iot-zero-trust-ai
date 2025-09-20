import React, { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Link, Navigate } from "react-router-dom";
import axios from "axios";
import DevicePage from "./pages/DevicePage";
import UserPage from "./pages/UserPage";
import GroupPage from "./pages/GroupPage";
import LoginPage from "./pages/LoginPage";
import { Layout, Menu, Button } from "antd";

const { Header, Content } = Layout;

function RequireAuth({ children }) {
  const token = localStorage.getItem("token");
  if (!token) {
    // not authenticated -> redirect to login
    return <Navigate to="/login" replace />;
  }
  return children;
}

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));

  useEffect(() => {
    // initialize axios Authorization header if token exists
    if (token) {
      axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common["Authorization"];
    }

    // simple interceptor to handle 401 globally: clear token and redirect to login
    const resInterceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response && error.response.status === 401) {
          localStorage.removeItem("token");
          delete axios.defaults.headers.common["Authorization"];
          // force reload to login page
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
    // navigate to login
    window.location.href = "/login";
  };

  const handleLoginSuccess = (newToken) => {
    // callback to set token state after login (LoginPage sets localStorage itself)
    setToken(newToken);
    axios.defaults.headers.common["Authorization"] = `Bearer ${newToken}`;
  };

  return (
    <BrowserRouter>
      <Layout style={{ minHeight: "100vh" }}>
        <Header style={{ display: "flex", alignItems: "center" }}>
          <div style={{ color: "white", fontSize: 20, marginRight: 40 }}>
            IoT Zero Trust AI Platform
          </div>

          <Menu
            theme="dark"
            mode="horizontal"
            defaultSelectedKeys={["devices"]}
            style={{ flex: 1 }}
          >
            <Menu.Item key="devices">
              <Link to="/">设备管理</Link>
            </Menu.Item>
            <Menu.Item key="users">
              <Link to="/users">用户管理</Link>
            </Menu.Item>
            <Menu.Item key="groups">
              <Link to="/groups">分组管理</Link>
            </Menu.Item>
          </Menu>

          <div style={{ marginLeft: 16 }}>
            {token ? (
              <Button type="primary" onClick={handleLogout}>
                退出登录
              </Button>
            ) : (
              <Link to="/login">
                <Button>登录</Button>
              </Link>
            )}
          </div>
        </Header>

        <Content style={{ padding: 24 }}>
          <Routes>
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
              element={<LoginPage onLoginSuccess={handleLoginSuccess} />}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Content>
      </Layout>
    </BrowserRouter>
  );
}

export default App;