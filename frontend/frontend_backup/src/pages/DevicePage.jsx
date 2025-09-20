import React, { useEffect, useState } from "react";
import { Table, Button, Modal, Form, Input, Select, message } from "antd";
import axios from "axios";

const { Option } = Select;

const api = "http://127.0.0.1:8000";

export default function DevicePage() {
  const [devices, setDevices] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);

  const [form] = Form.useForm();

  // 获取设备和用户
  const fetchDevices = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/devices/`);
      setDevices(res.data);
    } catch (e) {
      message.error("获取设备列表失败");
    }
    setLoading(false);
  };

  const fetchUsers = async () => {
    try {
      const res = await axios.get(`${api}/users/`);
      setUsers(res.data);
    } catch (e) {
      message.error("获取用户列表失败");
    }
  };

  useEffect(() => {
    fetchDevices();
    fetchUsers();
  }, []);

  // 新增设备
  const handleAddDevice = async () => {
    try {
      const values = await form.validateFields();
      if (users.length === 0) {
        message.error("请先添加用户后再添加设备！");
        return;
      }
      // owner_id 必须为数字，type、name与后端模型一致
      await axios.post(`${api}/devices/`, {
        name: values.name,
        type: values.type,
        owner_id: values.owner_id,
        // 如果有分组可以加 group_id: values.group_id
      });
      message.success("添加设备成功");
      setModalVisible(false);
      fetchDevices();
      form.resetFields();
    } catch (err) {
      // 优先显示后端返回的详细错误信息
      if (err.response && err.response.data && err.response.data.detail) {
        message.error(`添加失败: ${err.response.data.detail}`);
      } else {
        message.error("添加设备失败");
      }
    }
  };

  // 表格列
  const columns = [
    { title: "ID", dataIndex: "id", width: 60 },
    { title: "设备名", dataIndex: "name" },
    { title: "类型", dataIndex: "type" },
    { title: "状态", dataIndex: "status" },
    { title: "归属用户", dataIndex: "owner" },
    { title: "分组", dataIndex: "group" },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2>设备管理</h2>
      <Button
        type="primary"
        onClick={() => setModalVisible(true)}
        disabled={users.length === 0}
      >
        新增设备
      </Button>
      <Table
        columns={columns}
        dataSource={devices}
        rowKey="id"
        loading={loading}
        style={{ marginTop: 16 }}
      />

      <Modal
        title="新增设备"
        open={modalVisible}
        onOk={handleAddDevice}
        onCancel={() => setModalVisible(false)}
        okText="提交"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="设备名"
            name="name"
            rules={[{ required: true, message: "请输入设备名" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="类型"
            name="type"
            rules={[{ required: true, message: "请输入类型" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="归属用户"
            name="owner_id"
            rules={[{ required: true, message: "请选择用户" }]}
          >
            <Select
              placeholder={users.length === 0 ? "请先添加用户" : "请选择用户"}
              disabled={users.length === 0}
            >
              {users.map((u) => (
                <Option value={u.id} key={u.id}>
                  {u.username}
                </Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}