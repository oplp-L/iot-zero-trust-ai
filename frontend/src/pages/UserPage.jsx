import React, { useEffect, useState } from "react";
import { Table, Button, Modal, Form, Input, message } from "antd";
import axios from "axios";

const api = "http://127.0.0.1:8000";

export default function UserPage() {
  const [users, setUsers] = useState([]);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();

  // 获取用户列表
  const fetchUsers = async () => {
    try {
      const res = await axios.get(`${api}/users/`);
      setUsers(res.data);
    } catch (e) {
      message.error("获取用户列表失败");
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  // 新增用户
  const handleAddUser = async () => {
    try {
      const values = await form.validateFields();
      // 明确传递JSON字段，防止422错误
      await axios.post(`${api}/users/`, {
        username: values.username,
        password: values.password,
      });
      message.success("添加用户成功");
      setModalVisible(false);
      fetchUsers();
      form.resetFields();
    } catch (err) {
      // 兼容422结构和后端自定义报错
      if (err.response && err.response.data) {
        if (err.response.data.detail) {
          message.error(`添加失败: ${err.response.data.detail}`);
        } else if (typeof err.response.data === 'string') {
          message.error(`添加失败: ${err.response.data}`);
        } else {
          message.error("添加失败，用户名可能已存在");
        }
      } else {
        message.error("添加失败，用户名可能已存在");
      }
    }
  };

  const columns = [
    { title: "ID", dataIndex: "id", width: 60 },
    { title: "用户名", dataIndex: "username" },
    { title: "角色", dataIndex: "role" },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2>用户管理</h2>
      <Button type="primary" onClick={() => setModalVisible(true)}>
        新增用户
      </Button>
      <Table
        columns={columns}
        dataSource={users}
        rowKey="id"
        style={{ marginTop: 16 }}
      />

      <Modal
        title="新增用户"
        open={modalVisible}
        onOk={handleAddUser}
        onCancel={() => setModalVisible(false)}
        okText="提交"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item
            label="用户名"
            name="username"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}