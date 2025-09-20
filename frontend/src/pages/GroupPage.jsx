import React, { useEffect, useState } from "react";
import { Table, Button, Modal, Form, Input, message, Popconfirm } from "antd";
import axios from "axios";

const api = "http://127.0.0.1:8000";

export default function GroupPage() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();

  // 获取分组列表
  const fetchGroups = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${api}/groups/`);
      setGroups(res.data);
    } catch (e) {
      message.error("获取分组列表失败");
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchGroups();
  }, []);

  // 新增分组
  const handleAddGroup = async () => {
    try {
      const values = await form.validateFields();
      await axios.post(`${api}/groups/`, values);
      message.success("添加分组成功");
      setModalVisible(false);
      fetchGroups();
      form.resetFields();
    } catch (err) {
      if (err.response && err.response.data && err.response.data.detail) {
        message.error(`添加失败: ${err.response.data.detail}`);
      } else {
        message.error("添加失败，分组名可能已存在");
      }
    }
  };

  // 隔离分组
  const handleIsolate = async (id) => {
    try {
      const res = await axios.post(`${api}/groups/${id}/isolate`);
      message.success(res.data?.msg || "分组隔离成功");
      fetchGroups();
    } catch (e) {
      if (e.response && e.response.data && e.response.data.detail) {
        message.error(`隔离失败: ${e.response.data.detail}`);
      } else {
        message.error("隔离失败");
      }
    }
  };

  // 恢复分组
  const handleRestore = async (id) => {
    try {
      const res = await axios.post(`${api}/groups/${id}/restore`);
      message.success(res.data?.msg || "分组恢复成功");
      fetchGroups();
    } catch (e) {
      if (e.response && e.response.data && e.response.data.detail) {
        message.error(`恢复失败: ${e.response.data.detail}`);
      } else {
        message.error("恢复失败");
      }
    }
  };

  const columns = [
    { title: "ID", dataIndex: "id", width: 60 },
    { title: "分组名", dataIndex: "name" },
    { title: "描述", dataIndex: "description" },
    {
      title: "状态",
      dataIndex: "status",
      render: (text) => (text === "isolate" ? "已隔离" : "正常"),
    },
    {
      title: "操作",
      render: (_, row) => (
        <>
          <Popconfirm
            title="确定隔离该分组所有设备？"
            onConfirm={() => handleIsolate(row.id)}
          >
            <Button type="danger" size="small" style={{ marginRight: 8 }}>
              隔离
            </Button>
          </Popconfirm>
          <Popconfirm
            title="确定恢复该分组所有设备？"
            onConfirm={() => handleRestore(row.id)}
          >
            <Button type="primary" size="small">
              恢复
            </Button>
          </Popconfirm>
        </>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <h2>分组管理</h2>
      <Button type="primary" onClick={() => setModalVisible(true)}>
        新增分组
      </Button>
      <Table
        columns={columns}
        dataSource={groups}
        rowKey="id"
        loading={loading}
        style={{ marginTop: 16 }}
      />

      <Modal
        title="新增分组"
        open={modalVisible}
        onOk={handleAddGroup}
        onCancel={() => setModalVisible(false)}
        okText="提交"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item
            label="分组名"
            name="name"
            rules={[{ required: true, message: "请输入分组名" }]}
          >
            <Input />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}